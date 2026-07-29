import re
from core.logger import get_logger

logger = get_logger("SignalParser")

PRICE_TOKEN = r'\d[\d,]*(?:\.\d+)?'
PRICE_PATTERN = rf'({PRICE_TOKEN})'
ENTRY_SEPARATOR_PATTERN = r'(?:\s*(?:-|/|_|TO|\.\s*LIMIT\.?|\s+LIMIT\s+)\s*)'


def parse_price(price_text):
    """Parse a price, allowing thousands separators like 4,314."""
    return float(price_text.replace(',', ''))


def parse_entry_bound(bound_text):
    return parse_price(bound_text)


def parse_second_entry_bound(first_bound_text, second_bound_text):
    """Expand abbreviated ranges like 4006-08 into 4006-4008."""
    first_clean = first_bound_text.replace(',', '')
    second_clean = second_bound_text.replace(',', '')

    if (
        len(second_clean) < len(first_clean)
        and '.' not in first_clean
        and '.' not in second_clean
    ):
        prefix = first_clean[:-len(second_clean)]
        return float(prefix + second_clean)

    return parse_price(second_bound_text)


def extract_entry_bounds(fragment):
    range_match = re.search(
        PRICE_PATTERN + ENTRY_SEPARATOR_PATTERN + PRICE_PATTERN,
        fragment,
    )
    if range_match:
        bound1_text = range_match.group(1)
        bound2_text = range_match.group(2)
        return (
            parse_entry_bound(bound1_text),
            parse_second_entry_bound(bound1_text, bound2_text),
        )

    single_match = re.search(PRICE_PATTERN, fragment)
    if single_match:
        bound = parse_entry_bound(single_match.group(1))
        return bound, bound

    return None


def find_entry_bounds(text, direction):
    """Find entry from labels, zones, or the line containing BUY/SELL."""
    entry_labels = (
        r'ENTRY\s*(?:PRICE|ZONE)?',
        rf'{direction}\s+ZONE',
    )

    for label_pattern in entry_labels:
        for label_match in re.finditer(label_pattern, text):
            line_tail = text[label_match.end():].splitlines()[0]
            bounds = extract_entry_bounds(line_tail)
            if bounds:
                return bounds

    direction_matcher = re.compile(rf'(?<![A-Z0-9]){direction}(?![A-Z0-9])')
    for line in text.splitlines():
        direction_match = direction_matcher.search(line)
        if not direction_match:
            continue

        line_tail = line[direction_match.end():]
        bounds = extract_entry_bounds(line_tail)
        if bounds:
            return bounds

    return None


def find_first_tp(text):
    tp_label = re.compile(
        r'(?<![A-Z0-9])(?:'
        r'TP\s*(?:[-_ ]?[1-9]\d?)?(?!\d)|'
        r'TAKE\s*PROFIT\s*(?:TARGETS?)?\s*(?:[-_ ]?[1-9]\d?)?(?!\d)|'
        r'TAKEPROFIT\s*(?:[-_ ]?[1-9]\d?)?(?!\d)'
        r')(?![A-Z])'
    )

    for line in text.splitlines():
        label_match = tp_label.search(line)
        if not label_match:
            continue

        price_match = re.search(PRICE_PATTERN, line[label_match.end():])
        if price_match:
            return parse_price(price_match.group(1))

    return None


def find_sl(text):
    sl_label = re.compile(r'(?<![A-Z0-9])(?:SL|STOP\s*LOSS|STOPLOSS)(?![A-Z0-9])')

    for line in text.splitlines():
        label_match = sl_label.search(line)
        if not label_match:
            continue

        price_match = re.search(PRICE_PATTERN, line[label_match.end():])
        if price_match:
            return parse_price(price_match.group(1))

    return None


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

        if re.search(r'(?<![A-Z0-9])BUY(?![A-Z0-9])', text):
            signal['type'] = 'BUY'
        elif re.search(r'(?<![A-Z0-9])SELL(?![A-Z0-9])', text):
            signal['type'] = 'SELL'
        else:
            return None

        entry_bounds = find_entry_bounds(text, signal['type'])
        if not entry_bounds:
            logger.debug("Entry bounds not found in signal format.")
            return None

        bound1, bound2 = entry_bounds

        # Store raw bounds so executor can measure the range width
        signal['range_low'] = min(bound1, bound2)
        signal['range_high'] = max(bound1, bound2)

        # Determine entry price using the median of the two bounds
        signal['entry'] = (bound1 + bound2) / 2.0

        tp1 = find_first_tp(text)
        if tp1 is None:
            logger.warning("No TP1 found in signal. Ignoring.")
            return None
        signal['tp1'] = tp1

        sl = find_sl(text)
        if sl is None:
            logger.warning("No SL found in signal. Ignoring.")
            return None
        signal['sl'] = sl

        if not validate_signal_price_digits(signal):
            return None

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
