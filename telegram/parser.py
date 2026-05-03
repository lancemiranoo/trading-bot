import re
from core.logger import get_logger

logger = get_logger("SignalParser")

def parse_signal(text):
    """
    Parses a trading signal from Telegram.
    Expected format:
    SELL: 4578-4583
    TP1: 4573
    TP2: 4568
    TP3: 4563
    TP4: OPEN
    SL: 4593
    """
    try:
        text = text.upper()
        if "BUY" not in text and "SELL" not in text:
            return None

        signal = {}

        # Determine type and extract entry bounds
        if "SELL:" in text:
            signal['type'] = 'SELL'
            entry_match = re.search(r'SELL:\s*([\d.]+)\s*-\s*([\d.]+)', text)
        elif "BUY:" in text:
            signal['type'] = 'BUY'
            entry_match = re.search(r'BUY:\s*([\d.]+)\s*-\s*([\d.]+)', text)
        else:
            return None

        if not entry_match:
            logger.debug("Entry bounds not found in signal format.")
            return None

        bound1 = float(entry_match.group(1))
        bound2 = float(entry_match.group(2))
        
        # Determine strict entry price
        # For SELL, we want to sell at the upper bound.
        # For BUY, we want to buy at the lower bound.
        if signal['type'] == 'SELL':
            signal['entry'] = max(bound1, bound2)
        else:
            signal['entry'] = min(bound1, bound2)

        # Extract TP1 (mandatory)
        tp_match = re.search(r'TP1:\s*([\d.]+)', text)
        if not tp_match:
            logger.warning("No TP1 found in signal. Ignoring.")
            return None
        signal['tp1'] = float(tp_match.group(1))

        # Extract SL (mandatory)
        sl_match = re.search(r'SL:\s*([\d.]+)', text)
        if not sl_match:
            logger.warning("No SL found in signal. Ignoring.")
            return None
        signal['sl'] = float(sl_match.group(1))

        # Validate logic
        if signal['type'] == 'SELL':
            if signal['tp1'] >= signal['entry'] or signal['sl'] <= signal['entry']:
                logger.warning(f"Invalid SELL signal levels. Entry: {signal['entry']}, TP1: {signal['tp1']}, SL: {signal['sl']}")
                return None
        else: # BUY
            if signal['tp1'] <= signal['entry'] or signal['sl'] >= signal['entry']:
                logger.warning(f"Invalid BUY signal levels. Entry: {signal['entry']}, TP1: {signal['tp1']}, SL: {signal['sl']}")
                return None

        return signal

    except Exception as e:
        logger.error(f"Error parsing signal: {e}")
        return None
