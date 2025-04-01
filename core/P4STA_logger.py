import colorlog
import os

def create_logger(name=""):
    # check environment variable for logging
    if "P4STA_LOG_LEVEL" in os.environ:
        # defaulting to DEBUG
        if os.environ["P4STA_LOG_LEVEL"] == "INFO":
            level = colorlog.INFO
            lv = "INFO"
        else: # os.environ["P4STA_LOG_LEVEL"] == "DEBUG":
            level = colorlog.DEBUG
            lv = "DEBUG"
    else:
        print("ENV variable P4STA_LOG_LEVEL not found.")
        level = colorlog.DEBUG
        lv = "DEBUG"

    logger = colorlog.getLogger(__name__)
    logger.setLevel(level)

    handler = colorlog.StreamHandler()
    handler.setFormatter(colorlog.ColoredFormatter('%(log_color)s[%(asctime)s] %(levelname)s [' + name + ' %(filename)s.%(funcName)s:%(lineno)d] %(message)s', datefmt='%d/%b/%Y %H:%M:%S'))
    logger.addHandler(handler)

    logger.info("Set log level to: " + str(lv) + " for " + name)

    return logger

def test_logger(logger):
    logger.debug("Debug")
    logger.info("Information")
    logger.warning("Warning")
    logger.error("Error")
    logger.critical("Critical")