import os
import csv
import MetaTrader5 as mt5
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
        'Timestamp', 'Ticket', 'Symbol', 'Type', 'Status', 
        'Price', 'SL', 'TP', 'Profit', 'Loss', 'Channel'
    ]
    
    # Get current time in specified local timezone
    tz = pytz.timezone(config.DISPLAY_TIMEZONE)
    local_now = datetime.now(pytz.utc).astimezone(tz)
    
    row = {
        'Timestamp': local_now.strftime('%Y-%m-%d %H:%M:%S'),
        'Ticket': ticket,
        'Symbol': signal.get('symbol', config.SYMBOL), 
        'Type': signal.get('type'),
        'Status': 'OPEN',
        'Price': f"{price:.2f}" if price else "0.00",
        'SL': f"{signal.get('sl'):.2f}" if signal.get('sl') else "0.00",
        'TP': f"{signal.get('tp1'):.2f}" if signal.get('tp1') else "0.00",
        'Profit': "0.00",
        'Loss': "0.00",
        'Channel': channel_name
    }
    
    try:
        with open(TRADES_LOG_FILE, mode='a', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=headers)
            if not file_exists:
                writer.writeheader()
            writer.writerow(row)
    except Exception as e:
        print(f"CRITICAL ERROR: Could not write to trades.csv: {e}")

def log_closed_trade(deal):
    """
    Logs the closure of a trade including profit and result (Win/Loss).
    """
    file_exists = os.path.isfile(TRADES_LOG_FILE)
    headers = [
        'Timestamp', 'Ticket', 'Symbol', 'Type', 'Status', 
        'Price', 'SL', 'TP', 'Profit', 'Loss', 'Channel'
    ]
    
    tz = pytz.timezone(config.DISPLAY_TIMEZONE)
    local_now = datetime.now(pytz.utc).astimezone(tz)
    
    profit = deal.profit + deal.commission + deal.fee + deal.swap
    result = "WIN" if profit > 0 else "LOSS"
    
    row = {
        'Timestamp': local_now.strftime('%Y-%m-%d %H:%M:%S'),
        'Ticket': deal.position_id, # Link back to the position
        'Symbol': deal.symbol,
        'Type': 'BUY' if deal.type == mt5.DEAL_TYPE_SELL else 'SELL', # Closing a BUY is a DEAL_TYPE_SELL
        'Status': f"CLOSED ({result})",
        'Price': f"{deal.price:.2f}",
        'SL': "0.00", # SL/TP not directly in deal, but we have price
        'TP': "0.00",
        'Profit': f"{profit:.2f}" if profit > 0 else "0.00",
        'Loss': f"{abs(profit):.2f}" if profit < 0 else "0.00",
        'Channel': '-' 
    }
    
    try:
        with open(TRADES_LOG_FILE, mode='a', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=headers)
            if not file_exists:
                writer.writeheader()
            writer.writerow(row)
    except Exception as e:
        print(f"CRITICAL ERROR: Could not write closure to trades.csv: {e}")

def get_logged_tickets():
    """
    Returns a set of all trade tickets already present in the log file.
    """
    tickets = set()
    if not os.path.isfile(TRADES_LOG_FILE):
        return tickets
    
    try:
        with open(TRADES_LOG_FILE, mode='r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row['Ticket'] and row['Status'].startswith('CLOSED'):
                    tickets.add(int(row['Ticket']))
    except Exception as e:
        print(f"Error reading logged tickets: {e}")
    
    return tickets
