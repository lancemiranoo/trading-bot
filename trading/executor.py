import MetaTrader5 as mt5
from datetime import datetime, timedelta
from core import config
from core.logger import get_logger
from trading.trade_logger import log_trade

logger = get_logger("TradeExecutor")

def initialize_mt5():
    """Initializes and logs into the MetaTrader 5 terminal."""
    # Use explicit path to resolve IPC timeout issues
    mt5_path = "C:/Program Files/MetaTrader 5/terminal64.exe"
    if not mt5.initialize(path=mt5_path):
        logger.error(f"MT5 initialization failed at {mt5_path}. Error code: {mt5.last_error()}")
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

    # Fetch current market prices to determine validity
    tick = mt5.symbol_info_tick(symbol)
    if not tick:
        logger.error(f"Failed to get tick data for {symbol}.")
        return False

    sl = signal['sl']
    tp = signal['tp1']
    entry_price = signal['entry']

    if signal['type'] == 'BUY_LIMIT':
        action = mt5.ORDER_TYPE_BUY_LIMIT
        price = entry_price
        # Safety check: Is the price still between SL and TP?
        if price >= tp:
            logger.warning(f"Skipping BUY_LIMIT trade: Entry price ({price}) is already above or at TP ({tp}).")
            return False
        if price <= sl:
            logger.warning(f"Skipping BUY_LIMIT trade: Entry price ({price}) is already below or at SL ({sl}).")
            return False
        # For a BUY_LIMIT order, the current market price (ask) must be above the entry price.
        if tick.ask <= price:
            logger.warning(f"Skipping BUY_LIMIT trade: Current market price ({tick.ask}) is already at or below entry price ({price}).")
            return False
    elif signal['type'] == 'SELL_LIMIT':
        action = mt5.ORDER_TYPE_SELL_LIMIT
        price = entry_price
        # Safety check: Is the price still between SL and TP?
        if price <= tp:
            logger.warning(f"Skipping SELL_LIMIT trade: Entry price ({price}) is already below or at TP ({tp}).")
            return False
        if price >= sl:
            logger.warning(f"Skipping SELL_LIMIT trade: Entry price ({price}) is already above or at SL ({sl}).")
            return False
        # For a SELL_LIMIT order, the current market price (bid) must be below the entry price.
        if tick.bid >= price:
            logger.warning(f"Skipping SELL_LIMIT trade: Current market price ({tick.bid}) is already at or above entry price ({price}).")
            return False
    else:
        logger.error(f"Unknown signal type: {signal['type']}")
        return False

    # Clean the comment: normalize fancy unicode to standard ASCII, strip emojis, and truncate to MT5's 31-character limit
    import unicodedata
    raw_comment = f"TG_{channel_name}"
    normalized_comment = unicodedata.normalize('NFKD', raw_comment)
    clean_comment = "".join(c for c in normalized_comment if 32 <= ord(c) <= 126)[:31]

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
        "comment": clean_comment,
        "type_filling": mt5.ORDER_FILLING_RETURN,
    }

    # Add expiration if specified in config
    expiration_minutes = getattr(config, 'ORDER_EXPIRATION_MINUTES', None)
    if expiration_minutes:
        request["type_time"] = mt5.ORDER_TIME_SPECIFIED
        request["expiration"] = int(tick.time + expiration_minutes * 60)
    else:
        request["type_time"] = mt5.ORDER_TIME_GTC

    logger.info(f"Sending MT5 Order Request: {request}")
    result = mt5.order_send(request)
    if result is None:
        logger.error(f"MT5 order_send returned None. Last error: {mt5.last_error()}")
        return False

    if result.retcode != mt5.TRADE_RETCODE_DONE:
        # Provide more detailed error logging
        err_msg = f"Order failed, retcode={result.retcode}. Error: {result.comment}"
        if result.retcode == 10016:
            err_msg += " (Invalid stops - check if price is too close to SL/TP or if levels are swapped or if order price is invalid)"
        logger.error(err_msg)
        return False

    logger.info(f"Trade placed successfully: {signal['type']} Limit at {price}, SL: {sl}, TP: {tp}")
    # log_trade(signal, channel_name, price=price, ticket=result.order) # Disabled to only show CLOSED trades in CSV
    return True
