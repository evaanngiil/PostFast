import logging
import sys

class LogColors:
    RESET = "\033[0m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    PURPLE = "\033[95m"
    CYAN = "\033[96m"
    BOLD = "\033[1m"
    UNDERLINE = "\033[4m"

LOGS_COLORS = {
    logging.DEBUG: LogColors.CYAN,
    logging.INFO: LogColors.GREEN,
    logging.WARNING: LogColors.YELLOW,
    logging.ERROR: LogColors.RED,
    logging.CRITICAL: LogColors.BOLD + LogColors.RED
}

class ColoredFormatter(logging.Formatter):
    def format(self, record):
        log_color = LOGS_COLORS.get(record.levelno, LogColors.RESET)
        log_message = f"{self.formatTime(record, self.datefmt)} - {record.name} - {record.levelname} - {record.getMessage()}"
        return f"{log_color}{log_message}{LogColors.RESET}"

def get_logger(name="LangGraph"):
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)

    if logger.hasHandlers():
        return logger

    formatter = ColoredFormatter(fmt="%(asctime)s - %(name)s - %(levelname)s - %(message)s", datefmt="%Y-%m-%d %H:%M:%S")

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    return logger

logger = get_logger()
