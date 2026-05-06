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
    Retrieves original SL/TP and Channel info from history.
    """
    file_exists = os.path.isfile(TRADES_LOG_FILE)
    headers = [
        'Timestamp', 'Ticket', 'Symbol', 'Type', 'Status', 
        'Price', 'SL', 'TP', 'Profit', 'Loss', 'Channel'
    ]
    
    # 1. Fetch original Order to get SL, TP, and Channel Name
    # (Deals don't store SL/TP, so we must check the order that opened this position)
    orders = mt5.history_orders_get(position=deal.position_id)
    sl = 0.0
    tp = 0.0
    comment = "-"
    
    if orders:
        # Sort by time to get the first order (the opening one)
        first_order = sorted(orders, key=lambda x: x.time_setup)[0]
        sl = first_order.sl
        tp = first_order.tp
        comment = first_order.comment
    
    # Extract channel from comment (e.g., "TG_The MMM" -> "The MMM")
    channel_name = comment.replace("TG_", "") if (comment and comment.startswith("TG_")) else "-"
    if not channel_name or channel_name == "Signal_Bot": channel_name = "-"

    tz = pytz.timezone(config.DISPLAY_TIMEZONE)
    local_now = datetime.now(pytz.utc).astimezone(tz)
    
    profit = deal.profit + deal.commission + deal.fee + deal.swap
    result = "WIN" if profit > 0 else "LOSS"
    
    # Correct the Type: the deal.type for an OUT deal is the opposite of the position
    # If the position was BUY, the OUT deal is a SELL.
    pos_type = "SELL" if deal.type == mt5.DEAL_TYPE_BUY else "BUY"

    row = {
        'Timestamp': local_now.strftime('%Y-%m-%d %H:%M:%S'),
        'Ticket': deal.position_id,
        'Symbol': deal.symbol,
        'Type': pos_type,
        'Status': f"CLOSED ({result})",
        'Price': f"{deal.price:.2f}",
        'SL': f"{sl:.2f}",
        'TP': f"{tp:.2f}",
        'Profit': f"{profit:.2f}" if profit > 0 else "0.00",
        'Loss': f"{abs(profit):.2f}" if profit < 0 else "0.00",
        'Channel': channel_name
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
