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
ORDER_EXPIRATION_MINUTES = 30
FIXED_STOP_LOSS_PIPS = 700
XAUUSD_PIP_SIZE = 0.01

# Session Times (UTC)
# Asian Session: 00:00 - 09:00 UTC
# London Session: 08:00 - 17:00 UTC
# Combined range: 00:00 - 17:00 UTC
TRADING_SESSIONS = [
    {"name": "Asian", "start": "00:00", "end": "09:00"},
    {"name": "London", "start": "08:00", "end": "17:00"},
    {"name": "New York", "start": "13:00", "end": "22:00"},
    {"name": "Sydney", "start": "22:00", "end": "07:00"}
]

# ==========================================
# News Filter (https://www.financecalendar.com)
# ==========================================
NEWS_FILTER_ENABLED = True
FINANCECALENDAR_API_KEY = os.getenv('FINANCECALENDAR_API_KEY', '')   # optional, raises daily limit
NEWS_API_BASE = "https://www.financecalendar.com/wp-json/fc/v1"
NEWS_IMPACT = ["high", "medium"]   # block on high AND medium impact

# Only events that move gold (XAUUSD). Series codes from financecalendar.com /series.
NEWS_SERIES = [
    # Fed / interest rates
    "fomc",                     # FOMC rate decision (high)
    "fomc-minutes",             # FOMC minutes (medium)
    "fed-testimony",            # Fed Chair testimony (medium)
    "jackson-hole",             # Jackson Hole symposium (medium)
    # Inflation
    "us-cpi",                   # CPI (high)
    "us-pce",                   # PCE inflation (high)
    "us-ppi",                   # PPI (medium)
    "us-employment-cost-index", # Employment Cost Index (medium)
    # Jobs
    "us-nfp",                   # Non-Farm Payrolls (high)
    "us-unemployment",          # Unemployment rate (medium)
    "us-jobless-claims",        # Weekly jobless claims, Thursdays (medium)
    "us-adp",                   # ADP employment (medium)
    "us-jolts",                 # JOLTS job openings (medium)
    # Growth / activity
    "us-gdp",                   # GDP (high)
    "us-retail-sales",          # Retail sales (high)
    "us-ism-manufacturing",     # ISM Manufacturing PMI (high)
    "us-ism-services",          # ISM Services PMI (medium)
    "us-consumer-sentiment",    # UMich sentiment / inflation expectations (medium)
]
NEWS_BLOCK_BEFORE_MIN = 60         # stop trading 1 hour before
NEWS_BLOCK_AFTER_MIN = 60          # resume 1 hour after
NEWS_REFRESH_MINUTES = 60          # API caches 5 min; hourly is plenty
NEWS_LOOKAHEAD_DAYS = 7
NEWS_CANCEL_PENDING_ORDERS = True
NEWS_CLOSE_OPEN_POSITIONS = False
NEWS_UNTIMED_POLICY = "ignore"     # "ignore" | "block_day"
NEWS_FAIL_MODE = "block"           # "block" | "allow" when calendar data is stale
NEWS_MAX_CACHE_AGE_HOURS = 24
