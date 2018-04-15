import logging
import os
from logging.handlers import RotatingFileHandler

from discord_bot import cfg
from discord_bot import utils

CONF = cfg.CONF

LOG_PATTERN = logging.Formatter('%(asctime)s:%(levelname)s:%(name)s: [%(filename)s] %(message)s')


def setup():

    log_dir = utils.get_project_dir() + "/log"
    if not os.path.isdir(log_dir):
        os.makedirs(log_dir)

    # write in the console
    steam_handler = logging.StreamHandler()
    steam_handler.setFormatter(LOG_PATTERN)
    steam_handler.setLevel(logging.DEBUG)

    def setup_logger(logger_name, file_name=None, add_steam=False):
        file_name = file_name or logger_name

        logger = logging.getLogger(logger_name)
        logger.setLevel(logging.DEBUG)
        file_handler = RotatingFileHandler(log_dir + "/" + file_name + ".log", "a", 1000000, 1)
        file_handler.setFormatter(LOG_PATTERN)
        logger.addHandler(file_handler)
        if add_steam:
            logger.addHandler(steam_handler)

    setup_logger("discord")
    setup_logger("debug", CONF.CONF_NAME, True)
