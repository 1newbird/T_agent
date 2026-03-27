import math
import re

from langchain_core.embeddings import Embeddings

from skills_manager.base import SkillRetriever, SkillSelector
from skills_manager.types import (
    RetrievalCandidate,
    RetrievalResult,
    SelectionItem,
    SelectionResult,
    SkillMetadata,
    SkillSelectionRequest,
)


_WORD_RE = re.compile(r"\w+")


def _tokenize(text: str) -> set[str]:
    return set(_WORD_RE.findall(text.lower()))


def _keyword_candidates(skills: list[SkillMetadata], request: SkillSelectionRequest) -> list[RetrievalCandidate]:
    normalized_query = request.query_text.lower().strip()
    query_tokens = _tokenize(request.query_text)
    scored_candidates: list[RetrievalCandidate] = []

    for skill in skills:
        haystack = f"{skill.name} {skill.description}".lower()
        skill_tokens = _tokenize(haystack)
        overlap = len(query_tokens & skill_tokens)
        exact_bonus = 3 if normalized_query and normalized_query in haystack else 0
        score = overlap + exact_bonus
        if score == 0:
            continue
        scored_candidates.append(
            RetrievalCandidate(
                skill=skill,
                score=float(score),
                reason="keyword overlap",
                source="keyword",
            )
        )

    scored_candidates.sort(key=lambda item: ((item.score or 0), item.skill.name), reverse=True)
    return scored_candidates


def _cosine_similarity(left: list[float], right: list[float]) -> float:
    numerator = sum(a * b for a, b in zip(left, right, strict=False))
    left_norm = math.sqrt(sum(a * a for a in left))
    right_norm = math.sqrt(sum(b * b for b in right))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return numerator / (left_norm * right_norm)


class PassThroughRetriever(SkillRetriever):
    """
    粗筛方式1，不走提示词，不走 LLM，直接把全部 SkillMetadata 返回成候选，相当于就是不筛。
    """

    def retrieve(self, skills: list[SkillMetadata], request: SkillSelectionRequest) -> RetrievalResult:
        return RetrievalResult(
            mode="passthrough",
            all_skills_count=len(skills),
            candidates=[RetrievalCandidate(skill=skill, source="passthrough") for skill in skills],
        )


class KeywordRetriever(SkillRetriever):
    """
    粗筛方式2，只使用关键词重叠做召回，不调用 LLM。
    适合技能数量不多、命名清晰、需要可解释性的场景。
    """

    def retrieve(self, skills: list[SkillMetadata], request: SkillSelectionRequest) -> RetrievalResult:
        candidates = _keyword_candidates(skills, request)[: request.top_k_retrieval]
        return RetrievalResult(
            mode="keyword",
            all_skills_count=len(skills),
            candidates=candidates,
        )


class EmbeddingRetriever(SkillRetriever):
    """
    粗筛方式3，基于 skill metadata 的语义向量相似度做召回，不调用 LLM。
    适合补足关键词命中不到的同义表达和自然语言变体。
    """

    def __init__(self, embedding_model: Embeddings):
        self.embedding_model = embedding_model

    def retrieve(self, skills: list[SkillMetadata], request: SkillSelectionRequest) -> RetrievalResult:
        if not skills or not request.query_text.strip():
            return RetrievalResult(mode="embedding", all_skills_count=len(skills), candidates=[])

        query_vector = self.embedding_model.embed_query(request.query_text)
        doc_vectors = self.embedding_model.embed_documents(
            [f"{skill.name}\n{skill.description}" for skill in skills]
        )
        scored_candidates: list[RetrievalCandidate] = []

        for skill, vector in zip(skills, doc_vectors, strict=False):
            score = _cosine_similarity(query_vector, vector)
            if score <= 0:
                continue
            scored_candidates.append(
                RetrievalCandidate(
                    skill=skill,
                    score=score,
                    reason="embedding similarity",
                    source="embedding",
                )
            )

        scored_candidates.sort(key=lambda item: ((item.score or 0), item.skill.name), reverse=True)
        return RetrievalResult(
            mode="embedding",
            all_skills_count=len(skills),
            candidates=scored_candidates[: request.top_k_retrieval],
        )


class HybridRetriever(SkillRetriever):
    """
    粗筛方式4，采用 recall-first 的混合召回：
    先分别做 keyword 和 embedding 检索，再做并集去重；
    双命中的技能优先，剩余名额由 keyword-only 和 embedding-only 交替补位。
    目标是尽量减少漏召回，把最终判断交给后续 Selector。
    """

    def __init__(self, keyword_retriever: KeywordRetriever, embedding_retriever: EmbeddingRetriever):
        self.keyword_retriever = keyword_retriever
        self.embedding_retriever = embedding_retriever

    def retrieve(self, skills: list[SkillMetadata], request: SkillSelectionRequest) -> RetrievalResult:
        keyword_result = self.keyword_retriever.retrieve(skills, request)
        embedding_result = self.embedding_retriever.retrieve(skills, request)

        keyword_by_path = {candidate.skill.path: candidate for candidate in keyword_result.candidates}
        embedding_by_path = {candidate.skill.path: candidate for candidate in embedding_result.candidates}
        all_paths = list(dict.fromkeys([*keyword_by_path.keys(), *embedding_by_path.keys()]))

        both_hit: list[RetrievalCandidate] = []
        keyword_only: list[RetrievalCandidate] = []
        embedding_only: list[RetrievalCandidate] = []

        for path in all_paths:
            keyword_candidate = keyword_by_path.get(path)
            embedding_candidate = embedding_by_path.get(path)

            if keyword_candidate and embedding_candidate:
                both_hit.append(
                    RetrievalCandidate(
                        skill=keyword_candidate.skill,
                        score=max(keyword_candidate.score or 0.0, embedding_candidate.score or 0.0),
                        reason="hybrid keyword + embedding",
                        source="hybrid",
                    )
                )
                continue

            if keyword_candidate:
                keyword_only.append(keyword_candidate)
                continue

            if embedding_candidate:
                embedding_only.append(embedding_candidate)

        both_hit.sort(key=lambda item: item.skill.name)
        keyword_only.sort(key=lambda item: ((item.score or 0), item.skill.name), reverse=True)
        embedding_only.sort(key=lambda item: ((item.score or 0), item.skill.name), reverse=True)

        merged_candidates = list(both_hit)
        keyword_index = 0
        embedding_index = 0
        fill_keyword_next = True

        while len(merged_candidates) < request.top_k_retrieval:
            added = False

            if fill_keyword_next and keyword_index < len(keyword_only):
                merged_candidates.append(keyword_only[keyword_index])
                keyword_index += 1
                added = True
            elif not fill_keyword_next and embedding_index < len(embedding_only):
                merged_candidates.append(embedding_only[embedding_index])
                embedding_index += 1
                added = True
            elif keyword_index < len(keyword_only):
                merged_candidates.append(keyword_only[keyword_index])
                keyword_index += 1
                added = True
            elif embedding_index < len(embedding_only):
                merged_candidates.append(embedding_only[embedding_index])
                embedding_index += 1
                added = True

            if not added:
                break

            fill_keyword_next = not fill_keyword_next

        return RetrievalResult(
            mode="hybrid",
            all_skills_count=len(skills),
            candidates=merged_candidates[: request.top_k_retrieval],
        )


class KeywordLLMRetriever(SkillRetriever):
    """
    兼容模式：先用关键词召回 shortlist，再让 LLM 返回 top-k。
    这个实现保留给过渡阶段或对旧行为有依赖的场景，长期推荐优先使用 HybridRetriever + LLMSelector。
    """

    def __init__(self, llm):
        self.llm = llm

    def retrieve(self, skills: list[SkillMetadata], request: SkillSelectionRequest) -> RetrievalResult:
        scored_candidates = _keyword_candidates(skills, request)
        shortlist_limit = max(request.top_k_retrieval * 3, request.top_k_retrieval)
        shortlist = scored_candidates[:shortlist_limit]
        if not shortlist:
            return RetrievalResult(mode="keyword_llm", all_skills_count=len(skills), candidates=[])

        selected_names = self._select_top_k(shortlist, request)
        selected_candidates = []
        for candidate in shortlist:
            if candidate.skill.name not in selected_names:
                continue
            selected_candidates.append(
                RetrievalCandidate(
                    skill=candidate.skill,
                    score=candidate.score,
                    reason="keyword shortlist + llm top-k",
                    source="llm",
                )
            )
            if len(selected_candidates) >= request.top_k_retrieval:
                break

        return RetrievalResult(
            mode="keyword_llm",
            all_skills_count=len(skills),
            candidates=selected_candidates,
        )

    def _select_top_k(self, candidates: list[RetrievalCandidate], request: SkillSelectionRequest) -> list[str]:
        candidate_lines = [
            f"- {candidate.skill.name}: {candidate.skill.description}" for candidate in candidates
        ]
        prompt = (
            "你是一个 skills 粗筛器。\n"
            f"用户任务：{request.query_text}\n"
            f"请从下面候选中选出最相关的 {request.top_k_retrieval} 个 skill，"
            "只返回 skill 名称，每行一个，不要解释。\n\n"
            + "\n".join(candidate_lines)
        )
        response = self.llm.invoke(prompt)
        content = getattr(response, "content", response)
        if isinstance(content, list):
            content = "\n".join(str(item) for item in content)
        lines = [line.strip().lstrip("-*") for line in str(content).splitlines() if line.strip()]
        selected = []
        candidate_names = {candidate.skill.name for candidate in candidates}
        for line in lines:
            if line in candidate_names and line not in selected:
                selected.append(line)
            if len(selected) >= request.top_k_retrieval:
                break
        if selected:
            return selected
        return [candidate.skill.name for candidate in candidates[: request.top_k_retrieval]]


class LLMSelector(SkillSelector):
    """
    精判层，只在 Retriever 已经缩小范围的候选集上做最终选择。
    这一层负责“哪个技能最合适”，不负责目录扫描和技能正文加载。
    """

    def __init__(self, llm):
        self.llm = llm

    def select(self, candidates: list[RetrievalCandidate], request: SkillSelectionRequest) -> SelectionResult:
        if not candidates:
            return SelectionResult(input_candidates_count=0, selected=[])

        candidate_lines = [
            f"- {candidate.skill.name}: {candidate.skill.description}" for candidate in candidates
        ]
        prompt = (
            "你是一个 skills 精判器。\n"
            f"用户任务：{request.query_text}\n"
            f"请从下面候选中选择最合适的 {request.top_k_selection} 个 skill，"
            "只返回 skill 名称，每行一个，不要解释。\n\n"
            + "\n".join(candidate_lines)
        )
        response = self.llm.invoke(prompt)
        content = getattr(response, "content", response)
        if isinstance(content, list):
            content = "\n".join(str(item) for item in content)
        lines = [line.strip().lstrip("-*") for line in str(content).splitlines() if line.strip()]

        selected = []
        by_name = {candidate.skill.name: candidate for candidate in candidates}
        for line in lines:
            candidate = by_name.get(line)
            if candidate is None:
                continue
            selected.append(
                SelectionItem(
                    skill=candidate.skill,
                    score=candidate.score,
                    reason="llm fine selection",
                )
            )
            if len(selected) >= request.top_k_selection:
                break

        if not selected:
            fallback = candidates[: request.top_k_selection]
            selected = [
                SelectionItem(skill=candidate.skill, score=candidate.score, reason="fallback selection")
                for candidate in fallback
            ]

        return SelectionResult(input_candidates_count=len(candidates), selected=selected)
