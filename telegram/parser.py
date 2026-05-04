import re
from core.logger import get_logger

logger = get_logger("SignalParser")

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
            signal['type'] = 'BUY'
        elif "SELL" in text:
            signal['type'] = 'SELL'
        else:
            return None

        # Find Entry Price
        # Look for "Entry Price:", "Entry:", or just after BUY/SELL
        entry_match = re.search(r'ENTRY\s*(?:PRICE)?\s*[:]?\s*([\d.]+)(?:\s*-\s*([\d.]+))?', text)
        if not entry_match:
            # Handle "BUY NOW !" or "SELL NOW !"
            if signal['type'] == 'SELL':
                entry_match = re.search(r'SELL\s*(?:NOW\s*!)?\s*[:]?\s*([\d.]+)(?:\s*-\s*([\d.]+))?', text)
            else:
                entry_match = re.search(r'BUY\s*(?:NOW\s*!)?\s*[:]?\s*([\d.]+)(?:\s*-\s*([\d.]+))?', text)

        if not entry_match:
            logger.debug("Entry bounds not found in signal format.")
            return None

        bound1_str = entry_match.group(1)
        bound2_str = entry_match.group(2)

        bound1 = float(bound1_str)
        if bound2_str:
            # Handle abbreviated bounds like 4596-93 -> 4593
            if len(bound2_str) < len(bound1_str):
                prefix = bound1_str[:-len(bound2_str)]
                bound2 = float(prefix + bound2_str)
            else:
                bound2 = float(bound2_str)
        else:
            bound2 = bound1
        
        # Determine strict entry price
        if signal['type'] == 'SELL':
            signal['entry'] = max(bound1, bound2)
        else:
            signal['entry'] = min(bound1, bound2)

        # Extract TP1 (mandatory)
        # Matches TP, ITP, TP1, etc. handles dots like TP1. 
        tp_match = re.search(r'(?:I)?TP\s*(?:1)?\s*[:.]?\s*([\d.]+)', text)
        if not tp_match:
            tp_match = re.search(r'TP\s*[:.]?\s*([\d.]+)', text)
            
        if not tp_match:
            logger.warning("No TP1 found in signal. Ignoring.")
            return None
        signal['tp1'] = float(tp_match.group(1))

        # Extract SL (mandatory)
        # Matches SL or STOP LOSS, handles dots like SL.
        sl_match = re.search(r'SL\s*[:.]?\s*([\d.]+)', text)
        if not sl_match:
            sl_match = re.search(r'STOP\s*LOSS\s*(?:\(SL\))?\s*[:.]?\s*([\d.]+)', text)
            
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
