import os
import logging
from logging import handlers

# Logger setup
os.makedirs(os.environ.get('GUMO_LOG_FOLDER'), exist_ok=True)
filename = os.path.basename(os.environ.get('GUMO_CONFIG_FOLDER'))
log_pattern = logging.Formatter('%(asctime)s:%(levelname)s: %(message)s')

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# write in the console
steam_handler = logging.StreamHandler()
steam_handler.setFormatter(log_pattern)
steam_handler.setLevel(logging.DEBUG)
logger.addHandler(steam_handler)

# write into a file
filepath = f"{os.path.join(os.environ.get('GUMO_LOG_FOLDER'), filename)}.log"
file_handler = handlers.RotatingFileHandler(filepath, "a", 1000000, 1, encoding='utf-8')
file_handler.setFormatter(log_pattern)
steam_handler.setLevel(logging.DEBUG)
logger.addHandler(file_handler)

from .cfg import config
