import logging
import os
from logging.handlers import RotatingFileHandler


LOG_PATTERN = logging.Formatter('%(asctime)s:%(levelname)s: [%(filename)s] %(message)s')


def setup(log_dir, config_file):

    os.makedirs(log_dir, exist_ok=True)
    conf_filename = os.path.basename(config_file).rsplit(".", 1)[0]

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

    setup_logger("bot", conf_filename, True)
