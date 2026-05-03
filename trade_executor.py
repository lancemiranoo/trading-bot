import MetaTrader5 as mt5
from datetime import datetime, timedelta
import config
from logger import get_logger

logger = get_logger("TradeExecutor")

def initialize_mt5():
    """Initializes and logs into the MetaTrader 5 terminal."""
    if not mt5.initialize():
        logger.error(f"MT5 initialization failed. Error code: {mt5.last_error()}")
        return False

    if config.PAPER_TRADING:
        logger.info("Running in PAPER TRADING mode. Ensure you are connected to a demo account.")
    else:
        logger.warning("Running in LIVE TRADING mode.")

    # Authenticate
    authorized = mt5.login(config.MT5_LOGIN, password=config.MT5_PASSWORD, server=config.MT5_SERVER)
    if authorized:
        logger.info(f"Connected to MT5 account: {config.MT5_LOGIN} at {config.MT5_SERVER}")
        return True
    else:
        logger.error(f"Failed to connect to MT5 account. Error code: {mt5.last_error()}")
        return False

def execute_trade(signal, risk_manager):
    """
    Places a LIMIT order based on the parsed signal and risk parameters.
    """
    if not risk_manager.can_trade():
        logger.warning("Trade rejected by Risk Manager.")
        return False

    symbol = config.SYMBOL
    lot = config.LOT_SIZE

    # Ensure symbol is available
    if not mt5.symbol_select(symbol, True):
        logger.error(f"Failed to select symbol {symbol}.")
        return False

    action = mt5.ORDER_TYPE_BUY_LIMIT if signal['type'] == 'BUY' else mt5.ORDER_TYPE_SELL_LIMIT
    price = signal['entry']
    sl = signal['sl']
    tp = signal['tp1']

    # Set expiration time (e.g., 10 minutes from now)
    expiration = int((datetime.now() + timedelta(minutes=config.ORDER_EXPIRATION_MINUTES)).timestamp())

    request = {
        "action": mt5.TRADE_ACTION_PENDING,
        "symbol": symbol,
        "volume": lot,
        "type": action,
        "price": price,
        "sl": sl,
        "tp": tp,
        "deviation": 20,
        "magic": 123456,
        "comment": "TG_Signal_Bot",
        "type_time": mt5.ORDER_TIME_SPECIFIED,
        "expiration": expiration,
        "type_filling": mt5.ORDER_FILLING_RETURN,
    }

    logger.info(f"Sending MT5 Order Request: {request}")
    result = mt5.order_send(request)

    if result.retcode != mt5.TRADE_RETCODE_DONE:
        logger.error(f"Order failed, retcode={result.retcode}. Error: {result.comment}")
        return False

    logger.info(f"Trade placed successfully: {signal['type']} Limit at {price}, SL: {sl}, TP: {tp}")
    return True
