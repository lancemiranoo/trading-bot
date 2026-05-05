from telethon import TelegramClient, events
import asyncio
from core import config
from telegram.parser import parse_signal
from trading.executor import execute_trade
from core.logger import get_logger

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
    @client.on(events.MessageEdited(chats=chats_to_listen))
    async def new_message_handler(event):
        topic_id = None
        if event.message.reply_to:
            topic_id = getattr(event.message.reply_to, 'reply_to_top_id', None) or getattr(event.message.reply_to, 'reply_to_msg_id', None)

        # Topic Filtering Logic
        if hasattr(config, 'TOPIC_FILTERS') and config.TOPIC_FILTERS and event.chat_id in config.TOPIC_FILTERS:
            allowed_topics = config.TOPIC_FILTERS[event.chat_id]
            
            # If the message isn't in one of the allowed topics, ignore it.
            if topic_id not in allowed_topics:
                return

        text = event.message.text
        if not text:
            return

        chat = await event.get_chat()
        channel_name = getattr(chat, 'title', f"Unknown Channel ({event.chat_id})")
        
        logger.info(f"Incoming message from channel '{channel_name}': {text[:50]}...")

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

        # Execute the trade
        execute_trade(signal, risk_manager, channel_name)

    return client
