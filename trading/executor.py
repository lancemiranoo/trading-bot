import MetaTrader5 as mt5
from datetime import datetime, timedelta
from core import config
from core.logger import get_logger
from trading.trade_logger import log_trade

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

def execute_trade(signal, risk_manager, channel_name="Unknown"):
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

    # Fetch current market prices to determine LIMIT vs STOP
    tick = mt5.symbol_info_tick(symbol)
    if not tick:
        logger.error(f"Failed to get tick data for {symbol}.")
        return False

    if signal['type'] == 'BUY':
        action = mt5.ORDER_TYPE_BUY
        price = tick.ask
    else: # SELL
        action = mt5.ORDER_TYPE_SELL
        price = tick.bid

    sl = signal['sl']
    tp = signal['tp1']

    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "volume": lot,
        "type": action,
        "price": price,
        "sl": sl,
        "tp": tp,
        "deviation": 20,
        "magic": 123456,
        "comment": "TG_Signal_Bot",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }

    logger.info(f"Sending MT5 Order Request: {request}")
    result = mt5.order_send(request)

    if result.retcode != mt5.TRADE_RETCODE_DONE:
        err_msg = f"Order failed, retcode={result.retcode}. Error: {result.comment}"
        logger.error(err_msg)
        return False

    logger.info(f"Trade placed successfully: {signal['type']} Market at {price}, SL: {sl}, TP: {tp}")
    log_trade(signal, channel_name, price=price, ticket=result.order)
    return True
