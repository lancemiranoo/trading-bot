import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# ==========================================
# Telegram Configuration
# ==========================================
API_ID = int(os.getenv('API_ID', '0'))
API_HASH = os.getenv('API_HASH', '')
PHONE = os.getenv('PHONE', '')

# Comma-separated list of Telegram Channel IDs to listen to
_channel_ids_str = os.getenv('CHANNEL_IDS', '')
CHANNEL_IDS = [int(x.strip()) for x in _channel_ids_str.split(',') if x.strip()] if _channel_ids_str else []

# ==========================================
# MetaTrader 5 Configuration
# ==========================================
MT5_LOGIN = int(os.getenv('MT5_LOGIN', '0'))
MT5_PASSWORD = os.getenv('MT5_PASSWORD', '')
MT5_SERVER = os.getenv('MT5_SERVER', '')
PAPER_TRADING = os.getenv('PAPER_TRADING', 'True').lower() in ('true', '1', 't')

# ==========================================
# Trading Parameters
# ==========================================
SYMBOL = "XAUUSD"
LOT_SIZE = 0.01

# Risk Management
MAX_OPEN_TRADES = 5
DAILY_LOSS_LIMIT = 50.0  # In account currency (e.g., USD)
MAX_CONSECUTIVE_LOSSES = 4

# Trade Execution
ORDER_EXPIRATION_MINUTES = 10
