用户问：“帮我 review 一个 github PR，并总结风险”
Retriever 找到：
github_pr
code_review
risk_summary
Selector 最终选中：
github_pr
risk_summary
Loader 读到了这两个 SKILL.md
那么 payload 大概会像这样：


{
    "skill_candidates": [
        {
            "name": "github_pr",
            "description": "处理 GitHub PR 相关任务",
            "path": ".../skills/github_pr/SKILL.md",
            "score": 6.0,
            "reason": "hybrid keyword + embedding",
            "source": "hybrid",
        },
        {
            "name": "code_review",
            "description": "做通用代码审查",
            "path": ".../skills/code_review/SKILL.md",
            "score": 4.0,
            "reason": "keyword overlap",
            "source": "keyword",
        },
        {
            "name": "risk_summary",
            "description": "输出变更风险总结",
            "path": ".../skills/risk_summary/SKILL.md",
            "score": 0.84,
            "reason": "embedding similarity",
            "source": "embedding",
        },
    ],
    "selected_skills": [
        {
            "name": "github_pr",
            "description": "处理 GitHub PR 相关任务",
            "path": ".../skills/github_pr/SKILL.md",
            "score": 6.0,
            "reason": "llm fine selection",
        },
        {
            "name": "risk_summary",
            "description": "输出变更风险总结",
            "path": ".../skills/risk_summary/SKILL.md",
            "score": 0.84,
            "reason": "llm fine selection",
        },
    ],
    "loaded_skills": [
        {
            "name": "github_pr",
            "description": "处理 GitHub PR 相关任务",
            "path": ".../skills/github_pr/SKILL.md",
            "content": "---\\nname: github_pr\\ndescription: ...\\n---\\n这里是完整 skill 内容..."
        },
        {
            "name": "risk_summary",
            "description": "输出变更风险总结",
            "path": ".../skills/risk_summary/SKILL.md",
            "content": "---\\nname: risk_summary\\ndescription: ...\\n---\\n这里是完整 skill 内容..."
        },
    ]
}
现在它“怎么