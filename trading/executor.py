import MetaTrader5 as mt5
import unicodedata
from datetime import datetime, timedelta
from core import config
from core.logger import get_logger
from trading.trade_logger import log_trade

logger = get_logger("TradeExecutor")

# ──────────────────────────────────────────────────────────────────────────────
# If the gap between the signal's entry price and the current live market price
# is >= this value, the market has already moved far enough from the intended
# entry that placing a limit order is impractical → use a market order instead.
#
# Example: signal entry = 2330, live ask = 2332  →  gap = 2  →  market order
#          signal entry = 2330, live ask = 2331  →  gap = 1  →  limit order
# ──────────────────────────────────────────────────────────────────────────────
MARKET_EXECUTION_THRESHOLD = 2.0


def initialize_mt5():
    """Initializes and logs into the MetaTrader 5 terminal."""
    mt5_path = "C:/Program Files/MetaTrader 5/terminal64.exe"
    if not mt5.initialize(path=mt5_path):
        logger.error(f"MT5 initialization failed at {mt5_path}. Error code: {mt5.last_error()}")
        return False

    if config.PAPER_TRADING:
        logger.info("Running in PAPER TRADING mode. Ensure you are connected to a demo account.")
    else:
        logger.warning("Running in LIVE TRADING mode.")

    authorized = mt5.login(config.MT5_LOGIN, password=config.MT5_PASSWORD, server=config.MT5_SERVER)
    if authorized:
        logger.info(f"Connected to MT5 account: {config.MT5_LOGIN} at {config.MT5_SERVER}")
        return True
    else:
        logger.error(f"Failed to connect to MT5 account. Error code: {mt5.last_error()}")
        return False


def _clean_comment(channel_name: str) -> str:
    """Normalize channel name to a safe MT5 comment (max 31 chars, ASCII only)."""
    raw = f"TG_{channel_name}"
    normalized = unicodedata.normalize('NFKD', raw)
    return "".join(c for c in normalized if 32 <= ord(c) <= 126)[:31]


def _get_tick(symbol: str):
    """Return the latest tick for symbol, or None with a logged error."""
    tick = mt5.symbol_info_tick(symbol)
    if not tick:
        logger.error(f"Failed to get tick data for {symbol}.")
    return tick


def execute_trade(signal, risk_manager, channel_name="Unknown"):
    """
    Routes execution to either a market order or a limit order based on how
    far the current live price has moved from the signal's entry price.

    Rule:
        |live_price - signal_entry| >= MARKET_EXECUTION_THRESHOLD  →  market order
        |live_price - signal_entry| <  MARKET_EXECUTION_THRESHOLD  →  limit order

    For BUY signals the live price used is the ask.
    For SELL signals the live price used is the bid.

    Example:
        signal entry = 2330, live ask = 2332  →  gap = 2  →  market order
        signal entry = 2330, live ask = 2331  →  gap = 1  →  limit order

    Signal keys expected:
        type   – 'BUY' or 'SELL'
        entry  – signal entry price (mid-point when a range is given)
        tp1    – take-profit level
        sl     – stop-loss level
    """
    if not risk_manager.can_trade():
        logger.warning("Trade rejected by Risk Manager.")
        return False

    symbol = config.SYMBOL

    if not mt5.symbol_select(symbol, True):
        logger.error(f"Failed to select symbol {symbol}.")
        return False

    tick = _get_tick(symbol)
    if not tick:
        return False

    entry_price = signal['entry']
    direction   = signal['type']  # 'BUY' or 'SELL'

    # Use ask for BUY, bid for SELL — the price the trader would actually pay/receive
    market_price = tick.ask if direction == 'BUY' else tick.bid
    market_gap   = abs(market_price - entry_price)

    logger.info(
        f"Signal entry: {entry_price} | Live {'ask' if direction == 'BUY' else 'bid'}: {market_price} "
        f"| Gap: {market_gap:.5f} | Threshold: {MARKET_EXECUTION_THRESHOLD}"
    )

    if market_gap >= MARKET_EXECUTION_THRESHOLD:
        logger.info(f"Gap ({market_gap:.5f}) >= threshold → using MARKET execution.")
        return _execute_market_order(signal, symbol, tick, channel_name)
    else:
        logger.info(f"Gap ({market_gap:.5f}) < threshold → using LIMIT order.")
        return _execute_limit_order(signal, symbol, tick, channel_name)


# ──────────────────────────────────────────────────────────────────────────────
# Market order
# ──────────────────────────────────────────────────────────────────────────────

def _execute_market_order(signal, symbol: str, tick, channel_name: str) -> bool:
    """Places an instant market order (BUY or SELL) at the current bid/ask."""
    lot = config.LOT_SIZE
    sl = signal['sl']
    tp = signal['tp1']
    direction = signal['type']  # 'BUY' or 'SELL'

    if direction == 'BUY':
        action = mt5.ORDER_TYPE_BUY
        price = tick.ask
        # Safety: market must not already be above TP or below SL
        if price >= tp:
            logger.warning(f"Skipping BUY market order: ask ({price}) is already at/above TP ({tp}).")
            return False
        if price <= sl:
            logger.warning(f"Skipping BUY market order: ask ({price}) is already at/below SL ({sl}).")
            return False
    elif direction == 'SELL':
        action = mt5.ORDER_TYPE_SELL
        price = tick.bid
        if price <= tp:
            logger.warning(f"Skipping SELL market order: bid ({price}) is already at/below TP ({tp}).")
            return False
        if price >= sl:
            logger.warning(f"Skipping SELL market order: bid ({price}) is already at/above SL ({sl}).")
            return False
    else:
        logger.error(f"Unknown signal type for market order: {direction}")
        return False

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
        "comment": _clean_comment(channel_name),
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }

    logger.info(f"Sending MT5 MARKET Order Request: {request}")
    result = mt5.order_send(request)
    if result is None:
        logger.error(f"MT5 order_send returned None. Last error: {mt5.last_error()}")
        return False

    if result.retcode != mt5.TRADE_RETCODE_DONE:
        err_msg = f"Market order failed, retcode={result.retcode}. Error: {result.comment}"
        logger.error(err_msg)
        return False

    logger.info(f"MARKET order placed: {direction} at {price}, SL: {sl}, TP: {tp}")
    return True


# ──────────────────────────────────────────────────────────────────────────────
# Limit order  (original logic, unchanged)
# ──────────────────────────────────────────────────────────────────────────────

def _execute_limit_order(signal, symbol: str, tick, channel_name: str) -> bool:
    """Places a pending LIMIT order at the signal's entry mid-point price."""
    lot = config.LOT_SIZE
    sl = signal['sl']
    tp = signal['tp1']
    entry_price = signal['entry']
    direction = signal['type']  # 'BUY' or 'SELL'

    if direction == 'BUY':
        action = mt5.ORDER_TYPE_BUY_LIMIT
        price = entry_price
        if price >= tp:
            logger.warning(f"Skipping BUY_LIMIT: entry ({price}) is already at/above TP ({tp}).")
            return False
        if price <= sl:
            logger.warning(f"Skipping BUY_LIMIT: entry ({price}) is already at/below SL ({sl}).")
            return False
        if tick.ask <= price:
            logger.warning(f"Skipping BUY_LIMIT: market ask ({tick.ask}) is already at/below entry ({price}).")
            return False
    elif direction == 'SELL':
        action = mt5.ORDER_TYPE_SELL_LIMIT
        price = entry_price
        if price <= tp:
            logger.warning(f"Skipping SELL_LIMIT: entry ({price}) is already at/below TP ({tp}).")
            return False
        if price >= sl:
            logger.warning(f"Skipping SELL_LIMIT: entry ({price}) is already at/above SL ({sl}).")
            return False
        if tick.bid >= price:
            logger.warning(f"Skipping SELL_LIMIT: market bid ({tick.bid}) is already at/above entry ({price}).")
            return False
    else:
        logger.error(f"Unknown signal type for limit order: {direction}")
        return False

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
        "comment": _clean_comment(channel_name),
        "type_filling": mt5.ORDER_FILLING_RETURN,
    }

    expiration_minutes = getattr(config, 'ORDER_EXPIRATION_MINUTES', None)
    if expiration_minutes:
        request["type_time"] = mt5.ORDER_TIME_SPECIFIED
        request["expiration"] = int(tick.time + expiration_minutes * 60)
    else:
        request["type_time"] = mt5.ORDER_TIME_GTC

    logger.info(f"Sending MT5 LIMIT Order Request: {request}")
    result = mt5.order_send(request)
    if result is None:
        logger.error(f"MT5 order_send returned None. Last error: {mt5.last_error()}")
        return False

    if result.retcode != mt5.TRADE_RETCODE_DONE:
        err_msg = f"Limit order failed, retcode={result.retcode}. Error: {result.comment}"
        if result.retcode == 10016:
            err_msg += " (Invalid stops – check if price is too close to SL/TP or levels are swapped)"
        logger.error(err_msg)
        return False

    logger.info(f"LIMIT order placed: {direction} at {price}, SL: {sl}, TP: {tp}")
    # log_trade(signal, channel_name, price=price, ticket=result.order)  # Disabled – logs only closed trades
    return True
