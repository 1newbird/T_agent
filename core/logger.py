import logging
import sys

from core.config import settings

_initialized = False


def get_logger(name: str) -> logging.Logger:
    """
    统一日志工厂。
    首次调用时配置根 logger（handler + formatter），后续调用只返回子 logger。
    日志级别读取 settings.log_level。
    """
    global _initialized

    if not _initialized:
        root_logger = logging.getLogger()
        root_logger.setLevel(getattr(logging, settings.log_level.upper(), logging.INFO))

        if not root_logger.handlers:
            handler = logging.StreamHandler(sys.stderr)
            handler.setFormatter(
                logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
            )
            root_logger.addHandler(handler)

        _initialized = True

    return logging.getLogger(name)
