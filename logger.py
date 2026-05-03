import logging
import sys
import os

# Force stdout to be utf-8 to prevent charmap errors on Windows when printing emojis
if sys.platform == 'win32' and hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

# Create logs directory if it doesn't exist
os.makedirs('logs', exist_ok=True)

def get_logger(name):
    """
    Creates and returns a logger with both file and console handlers.
    """
    logger = logging.getLogger(name)
    
    # Prevent duplicate handlers if get_logger is called multiple times for the same name
    if not logger.handlers:
        logger.setLevel(logging.INFO)
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

        # Console Handler
        ch = logging.StreamHandler(sys.stdout)
        ch.setFormatter(formatter)
        logger.addHandler(ch)

        # File Handler
        fh = logging.FileHandler(os.path.join('logs', 'trading_bot.log'), encoding='utf-8')
        fh.setFormatter(formatter)
        logger.addHandler(fh)
        
    return logger
