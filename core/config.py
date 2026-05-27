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
DISPLAY_TIMEZONE = os.getenv('DISPLAY_TIMEZONE', 'America/Edmonton') # Default to Alberta, can be 'Asia/Manila'

# Comma-separated list of Telegram Channel IDs to listen to
# Can include topics like: -100123456789_7
_channel_ids_str = os.getenv('CHANNEL_IDS', '')
CHANNEL_IDS = []
TOPIC_FILTERS = {}

if _channel_ids_str:
    for x in _channel_ids_str.split(','):
        x = x.strip()
        if not x: continue
        if '_' in x:
            chat_id_str, topic_id_str = x.split('_')
            chat_id = int(chat_id_str)
            topic_id = int(topic_id_str)
            if chat_id not in TOPIC_FILTERS:
                TOPIC_FILTERS[chat_id] = []
            TOPIC_FILTERS[chat_id].append(topic_id)
            if chat_id not in CHANNEL_IDS:
                CHANNEL_IDS.append(chat_id)
        else:
            chat_id = int(x)
            if chat_id not in CHANNEL_IDS:
                CHANNEL_IDS.append(chat_id)

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

# Demo
SYMBOL = "XAUUSD"
LOT_SIZE = 0.01

# Live
# SYMBOL = "XAUUSD-STD"
# LOT_SIZE = 0.01

# Risk Management
MAX_OPEN_TRADES = 5
SESSION_LOSS_LIMIT = 50.0  # Loss limit per individual trading session (Asian/London)
MAX_CONSECUTIVE_LOSSES = 3

# Trade Execution
ORDER_EXPIRATION_MINUTES = 10

# Session Times (UTC)
# Asian Session: 00:00 - 09:00 UTC
# London Session: 08:00 - 17:00 UTC
# Combined range: 00:00 - 17:00 UTC
TRADING_SESSIONS = [
    {"name": "Asian", "start": "00:00", "end": "09:00"},
    {"name": "London", "start": "08:00", "end": "17:00"}
]
