import config
import logging
from logging.handlers import TimedRotatingFileHandler

logger = logging.getLogger('mshc_chat')
logger.setLevel(logging.INFO)
handler = TimedRotatingFileHandler(config.LOG_FILE, when = "midnight")
handler.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(filename)s:%(lineno)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)