import asyncio
import MetaTrader5 as mt5
import config
from logger import get_logger
from risk_manager import RiskManager
from trade_executor import initialize_mt5
from signal_listener import setup_listener
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
        
        # Check every 60 seconds
        await asyncio.sleep(60)

async def main():
    logger.info("Starting MT5 Telegram Trading Bot...")

    # 1. Initialize MT5
    if not initialize_mt5():
        logger.error("Failed to initialize MT5. Exiting application.")
        sys.exit(1)

    # 2. Initialize Risk Manager
    risk_manager = RiskManager()
    
    # 3. Setup Telegram Listener
    client = setup_listener(risk_manager)
    
    logger.info("Connecting to Telegram...")
    await client.start(phone=config.PHONE)
    
    # 4. Start Background Tasks
    monitor_task = asyncio.create_task(risk_monitor_loop(risk_manager))

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
