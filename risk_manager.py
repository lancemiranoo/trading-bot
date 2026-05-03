import MetaTrader5 as mt5
import config
from logger import get_logger
from datetime import datetime, timedelta

logger = get_logger("RiskManager")

class RiskManager:
    def __init__(self):
        self.consecutive_losses = 0
        self.daily_loss = 0.0
        self.last_reset_date = datetime.now().date()
        self.trading_paused = False

    def check_daily_reset(self):
        """Resets the daily counters if the day has changed."""
        current_date = datetime.now().date()
        if current_date != self.last_reset_date:
            self.daily_loss = 0.0
            self.consecutive_losses = 0
            self.last_reset_date = current_date
            self.trading_paused = False
            logger.info("Daily risk metrics reset.")

    def update_from_history(self):
        """
        Polls the MT5 history to update today's consecutive losses and daily loss.
        Must be called periodically.
        """
        self.check_daily_reset()
        if self.trading_paused:
            return

        from_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        to_date = datetime.now() + timedelta(days=1)
        
        deals = mt5.history_deals_get(from_date, to_date)
        if deals is None:
            logger.error(f"Failed to get history deals for risk check: {mt5.last_error()}")
            return

        daily_loss = 0.0
        consec_losses = 0

        # Process deals chronologically
        deals = sorted(deals, key=lambda x: x.time)
        for deal in deals:
            # We only care about OUT deals for the target symbol (trades closing)
            if deal.symbol == config.SYMBOL and deal.entry == mt5.DEAL_ENTRY_OUT:
                # Include commission, fee, and swap in the profit calculation
                profit = deal.profit + deal.commission + deal.fee + deal.swap
                if profit < 0:
                    daily_loss += abs(profit)
                    consec_losses += 1
                else:
                    consec_losses = 0

        self.daily_loss = daily_loss
        self.consecutive_losses = consec_losses

        if self.daily_loss >= config.DAILY_LOSS_LIMIT:
            logger.warning(f"Daily loss limit reached (${self.daily_loss:.2f}). Pausing trading.")
            self.trading_paused = True

        if self.consecutive_losses >= config.MAX_CONSECUTIVE_LOSSES:
            logger.warning(f"Max consecutive losses reached ({self.consecutive_losses}). Pausing trading.")
            self.trading_paused = True

    def can_trade(self):
        """Checks if placing a new trade is allowed based on risk parameters."""
        self.check_daily_reset()

        if self.trading_paused:
            logger.warning("Trading is currently paused due to risk limits.")
            return False

        # Check total open trades
        positions = mt5.positions_get(symbol=config.SYMBOL)
        orders = mt5.orders_get(symbol=config.SYMBOL)
        
        num_active = 0
        if positions: num_active += len(positions)
        if orders: num_active += len(orders)

        if num_active >= config.MAX_OPEN_TRADES:
            logger.warning(f"Max open trades reached ({config.MAX_OPEN_TRADES}). Cannot place new trade.")
            return False

        return True
