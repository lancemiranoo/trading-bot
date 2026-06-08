import re
from core.logger import get_logger

logger = get_logger("SignalParser")

PRICE_PATTERN = r'([\d,]+(?:\.\d+)?)'


def parse_price(price_text):
    """Parse a price, allowing thousands separators like 4,314."""
    return float(price_text.replace(',', ''))


def has_four_integer_digits(value):
    return len(str(int(abs(value)))) == 4


def validate_signal_price_digits(signal):
    invalid_fields = [
        name for name in ('entry', 'tp1', 'sl')
        if not has_four_integer_digits(signal[name])
    ]

    if invalid_fields:
        logger.warning(
            "Invalid signal ignored: entry, TP1, and SL must all be 4-digit "
            f"price levels. Invalid: {', '.join(invalid_fields)}. "
            f"Entry: {signal['entry']}, TP1: {signal['tp1']}, SL: {signal['sl']}"
        )
        return False

    return True


def parse_signal(text):

    try:
        text = text.upper()
        # Clean up
        text = text.replace('*', '')
        text = text.replace('：', ':')
        
        # Normalize superscripts (¹ -> 1, etc)
        superscripts = {'¹': '1', '²': '2', '³': '3', '⁴': '4', '⁵': '5'}
        for k, v in superscripts.items():
            text = text.replace(k, v)
        
        # Remove zero-width spaces and other invisible formatting characters
        text = re.sub(r'[\u200b\u200c\u200d\u200e\u200f\ufeff]', '', text)

        signal = {}

        if "BUY" in text:
            signal['type'] = 'BUY_LIMIT'
        elif "SELL" in text:
            signal['type'] = 'SELL_LIMIT'
        else:
            return None

        # Find Entry Price
        # Look for "Entry Price:", "Entry:", or just after BUY/SELL
        entry_match = re.search(r'ENTRY\s*(?:PRICE)?\s*[:]?\s*' + PRICE_PATTERN + r'(?:\s*-\s*' + PRICE_PATTERN + r')?', text)
        if not entry_match:
            # Handle "BUY NOW !" or "SELL NOW !"
            if signal['type'] == 'SELL_LIMIT':
                entry_match = re.search(r'SELL\s*(?:NOW\s*!)?\s*[:]?\s*' + PRICE_PATTERN + r'(?:\s*-\s*' + PRICE_PATTERN + r')?', text)
            else:
                entry_match = re.search(r'BUY\s*(?:NOW\s*!)?\s*[:]?\s*' + PRICE_PATTERN + r'(?:\s*-\s*' + PRICE_PATTERN + r')?', text)

        if not entry_match:
            logger.debug("Entry bounds not found in signal format.")
            return None

        bound1_str = entry_match.group(1)
        bound2_str = entry_match.group(2)

        bound1_clean = bound1_str.replace(',', '')
        bound1 = parse_price(bound1_str)
        if bound2_str:
            # Handle abbreviated bounds like 4596-93 -> 4593
            bound2_clean = bound2_str.replace(',', '')
            if len(bound2_clean) < len(bound1_clean):
                prefix = bound1_clean[:-len(bound2_clean)]
                bound2 = float(prefix + bound2_clean)
            else:
                bound2 = parse_price(bound2_str)
        else:
            bound2 = bound1
        
        # Determine entry price using the median of the two bounds
        signal['entry'] = (bound1 + bound2) / 2.0

        # Extract TP1 (mandatory)
        # Matches TP, ITP, TP1, etc. handles spaces, dots, colons, underscores and dashes.
        sep = r'(?:\s*[:_ -]\s*|\s*\.(?!\d)\s*|\s+)'
        tp_match = re.search(r'(?:I)?TP\s*(?:[-_ ]?1)' + sep + PRICE_PATTERN, text)
        if not tp_match:
            tp_match = re.search(r'(?:I)?TP\s*[:._-]?\s*' + PRICE_PATTERN, text)
            
        if not tp_match:
            logger.warning("No TP1 found in signal. Ignoring.")
            return None
        signal['tp1'] = parse_price(tp_match.group(1))

        # Extract SL (mandatory)
        # Matches SL or STOP LOSS, handles spaces, dots, colons, underscores and dashes.
        sl_match = re.search(r'SL\s*[:._-]?\s*' + PRICE_PATTERN, text)
        if not sl_match:
            sl_match = re.search(r'STOP\s*LOSS\s*(?:\(SL\))?\s*[:._-]?\s*' + PRICE_PATTERN, text)
            
        if not sl_match:
            logger.warning("No SL found in signal. Ignoring.")
            return None
        signal['sl'] = parse_price(sl_match.group(1))

        if not validate_signal_price_digits(signal):
            return None

        # Validate logic
        if signal['type'] == 'SELL_LIMIT':
            if signal['tp1'] >= signal['entry'] or signal['sl'] <= signal['entry']:
                logger.warning(f"Invalid SELL_LIMIT signal levels. Entry: {signal['entry']}, TP1: {signal['tp1']}, SL: {signal['sl']}")
                return None
        else: # BUY_LIMIT
            if signal['tp1'] <= signal['entry'] or signal['sl'] >= signal['entry']:
                logger.warning(f"Invalid BUY_LIMIT signal levels. Entry: {signal['entry']}, TP1: {signal['tp1']}, SL: {signal['sl']}")
                return None

        return signal

    except Exception as e:
        logger.error(f"Error parsing signal: {e}")
        return None
