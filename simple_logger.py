# coding: utf-8
import logging
from logging.handlers import TimedRotatingFileHandler
from logging.handlers import RotatingFileHandler
import time
import re


def make_logger(name: str, log_file: str = None) -> logging.Logger:
    logger = logging.getLogger(name=name)
    logger.setLevel('DEBUG')
    BASIC_FORMAT = "%(asctime)s:%(levelname)s:%(message)s"
    DATE_FORMAT = '%Y-%m-%d %H:%M:%S'

    formatter = logging.Formatter(BASIC_FORMAT, DATE_FORMAT)
    console = logging.StreamHandler()
    console.setFormatter(formatter)
    logger.addHandler(console)

    if log_file:
        file_handler = TimedRotatingFileHandler(filename=log_file, encoding='utf-8',
                                                when="D", interval=1, backupCount=7)  # 每天一个文件，保留7个备份
        file_handler.setFormatter(formatter)
        file_handler.setLevel('INFO')
        logger.addHandler(file_handler)
    return logger
