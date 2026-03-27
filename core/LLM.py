from langchain.chat_models import init_chat_model
from langchain.embeddings import init_embeddings
import logging
from core.config import settings

logging.basicConfig(
    level=logging.INFO,  # 设置最低级别
    format='%(asctime)s - %(levelname)s - %(message)s'
)


def init_llm():
    """
    初始化LLM模型
    return:LLM实例
    """
    try:
        llm=init_chat_model(
            model=settings.chat_model_name,
            model_provider=settings.model_provider,
            base_url=settings.base_url,
            api_key=settings.chat_api_key
        )
        logging.info("模型初始化完成")
    except Exception as e:
        raise Exception(f"模型初始化失败：{str(e)}")
    return llm


def init_embedding_model():
    """
    初始化嵌入模型，供记忆检索等场景复用。
    """
    try:
        embedding_model = init_embeddings(
            model=settings.embed_model_name,
            model_provider=settings.model_provider,
            base_url=settings.base_url,
            api_key=settings.embed_api_key
        )
        logging.info("嵌入模型初始化完成")
        logging.info(f"当前嵌入模型: {settings.embed_model_name}")
    except Exception as e:
        raise Exception(f"嵌入模型初始化失败：{str(e)}")
    return embedding_model

if __name__=="__main__":
    llm=init_llm()
    ans=llm.invoke("你好啊，你是谁")
    print(ans)