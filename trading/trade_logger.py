import os
import csv
from datetime import datetime
import pytz
from core.logger import LOG_DIR
from core import config

TRADES_LOG_FILE = os.path.join(LOG_DIR, 'trades.csv')

def log_trade(signal, channel_name, price=None, ticket=None):
    """
    Logs successful trade details to a CSV file for tracking and analysis.
    """
    file_exists = os.path.isfile(TRADES_LOG_FILE)
    
    # Define headers
    headers = [
        'Timestamp', 'Channel', 'Symbol', 'Type', 'Entry_Signal', 
        'SL', 'TP1', 'Executed_Price', 'Ticket'
    ]
    
    # Get current time in specified local timezone
    tz = pytz.timezone(config.DISPLAY_TIMEZONE)
    local_now = datetime.now(pytz.utc).astimezone(tz)
    
    row = {
        'Timestamp': local_now.strftime('%Y-%m-%d %H:%M:%S'),
        'Channel': channel_name,
        'Symbol': signal.get('symbol', config.SYMBOL), 
        'Type': signal.get('type'),
        'Entry_Signal': signal.get('entry'),
        'SL': signal.get('sl'),
        'TP1': signal.get('tp1'),
        'Executed_Price': price,
        'Ticket': ticket
    }
    
    try:
        with open(TRADES_LOG_FILE, mode='a', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=headers)
            if not file_exists:
                writer.writeheader()
            writer.writerow(row)
    except Exception as e:
        # We don't want the whole bot to crash if logging fails
        print(f"CRITICAL ERROR: Could not write to trades.csv: {e}")
