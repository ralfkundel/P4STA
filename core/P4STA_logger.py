import colorlog
import os


def create_logger(name=""):
    if os.environ.get("P4STA_LOG_LEVEL") == "INFO":
        level = colorlog.INFO
        lv = "INFO"
    else:
        level = colorlog.DEBUG
        lv = "DEBUG"

    logger = colorlog.getLogger(name)
    logger.setLevel(level)
    logger.propagate = False

    if not logger.handlers:
        handler = colorlog.StreamHandler()
        handler.setFormatter(
            colorlog.ColoredFormatter(
                "%(log_color)s[%(asctime)s] %(levelname)s "
                "[%(name)s %(filename)s.%(funcName)s:%(lineno)d] %(message)s",
                datefmt="%d/%b/%Y %H:%M:%S"
            )
        )
        logger.addHandler(handler)

    logger.info("Set log level to: %s for %s", lv, name)
    return logger

def test_logger(logger):
    logger.debug("Debug")
    logger.info("Information")
    logger.warning("Warning")
    logger.error("Error")
    logger.critical("Critical")