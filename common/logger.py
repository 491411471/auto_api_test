import logging
import os
from logging.handlers import RotatingFileHandler
from concurrent_log_handler import ConcurrentRotatingFileHandler

# 控制台颜色代码（可选）
class ColoredFormatter(logging.Formatter):
    """为不同日志级别添加颜色"""
    grey = "\x1b[38;20m"
    yellow = "\x1b[33;20m"
    red = "\x1b[31;20m"
    bold_red = "\x1b[31;1m"
    reset = "\x1b[0m"

    FORMATS = {
        logging.DEBUG: grey + "%(asctime)s - %(name)s - DEBUG - %(message)s" + reset,
        logging.INFO: grey + "%(asctime)s - %(name)s - INFO - %(message)s" + reset,
        logging.WARNING: yellow + "%(asctime)s - %(name)s - WARNING - %(message)s" + reset,
        logging.ERROR: red + "%(asctime)s - %(name)s - ERROR - %(message)s" + reset,
        logging.CRITICAL: bold_red + "%(asctime)s - %(name)s - CRITICAL - %(message)s" + reset,
    }

    def format(self, record):
        log_fmt = self.FORMATS.get(record.levelno)
        formatter = logging.Formatter(log_fmt)
        return formatter.format(record)

def setup_logger(name=__name__, log_file='logs/api_test.log', level=logging.INFO):
    """设置logger，防止重复添加handler"""
    os.makedirs('logs', exist_ok=True)
    logger = logging.getLogger(name)
    
    # 防止重复添加handler（关键修复）
    if logger.handlers:
        return logger
    
    logger.setLevel(level)
    logger.propagate = False

    # 控制台 handler（带颜色）
    console = logging.StreamHandler()
    console.setLevel(level)
    console.setFormatter(ColoredFormatter())
    logger.addHandler(console)

    # 文件 handler（轮转，10MB）
    file_handler = ConcurrentRotatingFileHandler(
        log_file,
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
        encoding='utf-8'
    )
    file_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(file_formatter)
    logger.addHandler(file_handler)

    return logger

import colorama
colorama.init()
logger = setup_logger()