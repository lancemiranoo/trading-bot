import asyncio
import MetaTrader5 as mt5
from core import config
from core.logger import get_logger
from trading.risk_manager import RiskManager
from trading.executor import initialize_mt5, cancel_bot_pending_orders, close_bot_positions
from trading.news_filter import NewsFilter, describe, banner
from datetime import datetime, timezone, timedelta
from telegram.listener import setup_listener
import sys

logger = get_logger("Main")

async def risk_monitor_loop(risk_manager):
    """
    Background task to periodically sync the risk manager with MT5 history
    and check for daily/consecutive loss limits.
    """
    while True:
        try:
            risk_manager.update_from_history()
        except Exception as e:
            logger.error(f"Error in risk monitor loop: {e}")
        
        # Check every 5 seconds for faster logging
        await asyncio.sleep(5)

async def news_loop(news_filter):
    """
    Refreshes the news calendar periodically and, when a high-impact news
    blackout starts, cancels the bot's pending orders (optionally closes positions).
    """
    while True:
        try:
            now = datetime.now(timezone.utc)
            last = news_filter.last_refresh_attempt
            if last is None or now - last >= timedelta(minutes=config.NEWS_REFRESH_MINUTES) \
                    or (news_filter.last_success is None and now - last >= timedelta(minutes=5)):
                await asyncio.to_thread(news_filter.refresh)

            ev = news_filter.active_event()
            if ev and not news_filter.in_blackout:
                lines = [describe(ev), "The bot will NOT place trades until this window ends."]
                if config.NEWS_CANCEL_PENDING_ORDERS:
                    n = cancel_bot_pending_orders(config.SYMBOL)
                    lines.append(f"Cancelled {n} pending order(s).")
                if config.NEWS_CLOSE_OPEN_POSITIONS:
                    n = close_bot_positions(config.SYMBOL)
                    lines.append(f"Closed {n} open position(s).")
                logger.warning(banner("NO TRADING - GOLD NEWS", lines))
            elif not ev and news_filter.in_blackout:
                logger.info(banner("GOLD NEWS WINDOW OVER - TRADING RESUMED", []))
            elif ev and news_filter.in_blackout:
                # Reminder every ~10 minutes while paused
                if now.minute % 10 == 0 and now.second < 30:
                    logger.warning(f"Still NOT TRADING - gold news: {describe(ev)}")
            news_filter.in_blackout = bool(ev)
        except Exception as e:
            logger.error(f"Error in news loop: {e}")
        await asyncio.sleep(30)


async def main():
    logger.info("Starting MT5 Telegram Trading Bot...")

    # 1. Initialize MT5
    if not initialize_mt5():
        logger.error("Failed to initialize MT5. Exiting application.")
        sys.exit(1)

    # 2. Initialize Risk Manager
    news_filter = None
    if config.NEWS_FILTER_ENABLED:
        news_filter = NewsFilter()
        news_filter.refresh()
        upcoming = news_filter.upcoming_events()
        if upcoming:
            logger.info(banner(f"GOLD NEWS - bot will NOT trade during these windows (next {config.NEWS_LOOKAHEAD_DAYS} days)",
                               [describe(e) for e in upcoming]))
        else:
            logger.info("No gold news found in the next few days. Trading is not restricted by news.")
    risk_manager = RiskManager(news_filter)
    
    # 3. Setup Telegram Listener
    client = setup_listener(risk_manager)
    
    logger.info("Connecting to Telegram...")
    await client.start(phone=config.PHONE)
    
    # 4. Start Background Tasks
    monitor_task = asyncio.create_task(risk_monitor_loop(risk_manager))
    if news_filter:
        news_task = asyncio.create_task(news_loop(news_filter))

    logger.info("Bot is running and listening for signals. Press Ctrl+C to stop.")
    
    # Run Telegram client
    await client.run_until_disconnected()

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by manual kill switch (KeyboardInterrupt).")
    except Exception as e:
        logger.error(f"Bot stopped due to unexpected error: {e}")
    finally:
        mt5.shutdown()
        logger.info("MT5 connection closed gracefully.")
