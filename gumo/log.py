import logging
from logging.handlers import RotatingFileHandler
import os


LOG_PATTERN = logging.Formatter('%(asctime)s:%(levelname)s: %(message)s')


def setup(log_dir, config_dir):

    os.makedirs(log_dir, exist_ok=True)
    config_dirname = os.path.basename(config_dir)

    # write in the console
    steam_handler = logging.StreamHandler()
    steam_handler.setFormatter(LOG_PATTERN)
    steam_handler.setLevel(logging.DEBUG)

    def setup_logger(logger_name, file_name=None, add_steam=False):
        file_name = file_name or logger_name
        log_filename = f"{os.path.join(log_dir, file_name)}.log"

        logger = logging.getLogger(logger_name)
        logger.setLevel(logging.DEBUG)
        file_handler = RotatingFileHandler(log_filename, "a", 1000000, 1)
        file_handler.setFormatter(LOG_PATTERN)
        logger.addHandler(file_handler)
        if add_steam:
            logger.addHandler(steam_handler)

    setup_logger("bot", config_dirname, True)
