from telethon import TelegramClient, events
import asyncio
import config
from signal_parser import parse_signal
from trade_executor import execute_trade
from logger import get_logger

logger = get_logger("SignalListener")

# Keeps track of recently processed signals to avoid duplicates
processed_signals = set()

def setup_listener(risk_manager):
    """
    Sets up the event handler for incoming Telegram messages.
    """
    # Initialize Telethon Client inside the active event loop
    client = TelegramClient('trading_bot_session', config.API_ID, config.API_HASH)

    # Only listen to specific channels if they are configured
    chats_to_listen = config.CHANNEL_IDS if config.CHANNEL_IDS else None

    @client.on(events.NewMessage(chats=chats_to_listen))
    async def new_message_handler(event):
        text = event.message.text
        if not text:
            return

        logger.info(f"Incoming message from channel {event.chat_id}: {text[:50]}...")

        # Parse the message
        signal = parse_signal(text)
        if not signal:
            logger.debug("Message ignored: Not a valid trading signal.")
            return

        # Deduplication based on signal parameters
        sig_hash = f"{signal['type']}_{signal['entry']}_{signal['sl']}_{signal['tp1']}"
        if sig_hash in processed_signals:
            logger.info("Duplicate signal received, ignoring.")
            return

        processed_signals.add(sig_hash)
        logger.info(f"Valid signal parsed successfully: {signal}")

        # Execute the trade (runs synchronously, so it doesn't block async loop too much, 
        # but could be offloaded to an executor in a heavy traffic environment)
        execute_trade(signal, risk_manager)

    return client
