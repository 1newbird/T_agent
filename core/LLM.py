from langchain.chat_models import init_chat_model
from langchain.embeddings import init_embeddings

from core.config import settings
from core.logger import get_logger

logger = get_logger(__name__)

_llm_instance = None
_embedding_instance = None


def init_llm():
    """
    初始化 LLM 模型（单例缓存，多次调用返回同一实例）。
    """
    global _llm_instance
    if _llm_instance is not None:
        return _llm_instance

    try:
        _llm_instance = init_chat_model(
            model=settings.chat_model_name,
            model_provider=settings.model_provider,
            base_url=settings.base_url,
            api_key=settings.chat_api_key,
        )
        logger.info("LLM 模型初始化完成: %s", settings.chat_model_name)
    except Exception as e:
        raise Exception(f"LLM 模型初始化失败：{e}") from e
    return _llm_instance


def init_embedding_model():
    """
    初始化嵌入模型（单例缓存，多次调用返回同一实例）。
    """
    global _embedding_instance
    if _embedding_instance is not None:
        return _embedding_instance

    try:
        model_string = f"{settings.model_provider}:{settings.embed_model_name}"
        _embedding_instance = init_embeddings(
            model=model_string,
            base_url=settings.base_url,
            api_key=settings.embed_api_key,
        )
        logger.info("嵌入模型初始化完成: %s", settings.embed_model_name)
    except Exception as e:
        raise Exception(f"嵌入模型初始化失败：{e}") from e
    return _embedding_instance


if __name__ == "__main__":
    llm = init_llm()
    ans = llm.invoke("你好啊，你是谁")
    logger.info(ans)
