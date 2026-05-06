import MetaTrader5 as mt5
from core import config
from core.logger import get_logger
from datetime import datetime, timedelta, timezone
import pytz
from trading.trade_logger import log_closed_trade, get_logged_tickets

logger = get_logger("RiskManager")

class RiskManager:
    def __init__(self):
        self.last_reset_date = datetime.now().date()
        self.current_session = None
        self.session_loss = 0.0
        self.consecutive_losses = 0
        self.trading_paused = False
        
        # Initialize processed deals from CSV
        self.processed_deals = get_logged_tickets() 
        
        # ALSO: Snapshot current history and mark everything currently there as "processed"
        # This ensures we ONLY log brand-new trades that happen after the bot starts.
        now = datetime.now()
        from_date = now - timedelta(hours=48)
        to_date = now + timedelta(hours=24)
        existing_deals = mt5.history_deals_get(from_date, to_date)
        if existing_deals:
            for deal in existing_deals:
                self.processed_deals.add(deal.position_id)
        
        logger.info(f"RiskManager initialized. Ignoring {len(existing_deals) if existing_deals else 0} historical deals.")

    def check_daily_reset(self):
        """Resets the daily counters if the day has changed."""
        current_date = datetime.now().date()
        if current_date != self.last_reset_date:
            self.session_loss = 0.0
            self.consecutive_losses = 0
            self.last_reset_date = current_date
            self.trading_paused = False
            self.current_session = None # Force re-evaluation
            logger.info("Daily risk metrics reset.")

    def update_from_history(self):
        """
        Polls the MT5 history to log closed trades and update risk counters.
        """
        self.check_daily_reset()
        
        # --- 1. ALWAYS check history for logging closed trades ---
        # We use a very wide range to handle broker timezone differences (UTC+2/3/etc)
        now = datetime.now()
        from_date = now - timedelta(hours=48)
        to_date = now + timedelta(hours=24) # Look into the "future" to catch broker server time
        
        deals = mt5.history_deals_get(from_date, to_date)
        if deals is None:
            logger.error(f"Failed to get history deals: {mt5.last_error()}")
            return

        # Process deals chronologically for logging
        deals = sorted(deals, key=lambda x: x.time)
        for deal in deals:
            # Match symbol (case-insensitive) and look for OUT deals (closings)
            if config.SYMBOL.upper() in deal.symbol.upper() and deal.entry == mt5.DEAL_ENTRY_OUT:
                # Log if it's a new position closure we haven't seen yet
                if deal.position_id not in self.processed_deals:
                    logger.info(f"Detected newly closed trade: Ticket {deal.position_id}, Symbol {deal.symbol}, Profit {deal.profit}")
                    log_closed_trade(deal)
                    self.processed_deals.add(deal.position_id)

        # --- 2. SESSION-SPECIFIC risk calculations ---
        in_session, session_info = self.is_in_trading_session()
        if not in_session:
            self.current_session = None
            return

        session_name = session_info['name']
        
        # Reset if we just entered a new session
        if self.current_session != session_name:
            if self.current_session is not None:
                logger.info(f"New session detected: {session_name}. Resetting session risk counters.")
            self.session_loss = 0.0
            self.consecutive_losses = 0
            self.trading_paused = False
            self.current_session = session_name

        # Calculate session risk based on session start time
        now_utc = datetime.now(timezone.utc)
        start_time_str = session_info['start']
        start_time_dt = datetime.strptime(start_time_str, "%H:%M").time()
        session_start = now_utc.replace(hour=start_time_dt.hour, minute=start_time_dt.minute, second=0, microsecond=0)
        if session_start > now_utc:
            session_start -= timedelta(days=1)

        # Session-specific risk counters
        session_start_ts = session_start.timestamp()
        session_loss = 0.0
        consec_losses = 0

        for deal in deals:
            if config.SYMBOL.upper() in deal.symbol.upper() and deal.entry == mt5.DEAL_ENTRY_OUT:
                # Only count deals that closed AFTER this session started
                if deal.time >= session_start_ts:
                    profit = deal.profit + deal.commission + deal.fee + deal.swap
                    if profit < 0:
                        session_loss += abs(profit)
                        consec_losses += 1
                    else:
                        consec_losses = 0

        self.session_loss = session_loss
        self.consecutive_losses = consec_losses

        if self.session_loss >= config.SESSION_LOSS_LIMIT:
            if not self.trading_paused:
                logger.warning(f"Session loss limit reached (${self.session_loss:.2f}) for {session_name}. Pausing until next session.")
            self.trading_paused = True

        if self.consecutive_losses >= config.MAX_CONSECUTIVE_LOSSES:
            if not self.trading_paused:
                logger.warning(f"Max consecutive losses reached ({self.consecutive_losses}). Pausing until next session.")
            self.trading_paused = True

    def is_in_trading_session(self):
        """Checks if the current UTC time is within the allowed trading sessions."""
        now_utc = datetime.now(timezone.utc).time()
        
        for session in config.TRADING_SESSIONS:
            start_time = datetime.strptime(session['start'], "%H:%M").time()
            end_time = datetime.strptime(session['end'], "%H:%M").time()
            
            # Handle sessions that cross midnight (e.g., 22:00 to 04:00)
            if start_time <= end_time:
                if start_time <= now_utc <= end_time:
                    return True, session
            else: # Crosses midnight
                if now_utc >= start_time or now_utc <= end_time:
                    return True, session
        
        return False, None

    def can_trade(self):
        """Checks if placing a new trade is allowed based on risk parameters."""
        self.check_daily_reset()

        if self.trading_paused:
            logger.warning("Trading is currently paused due to risk limits.")
            return False

        # Session Check
        in_session, session_info = self.is_in_trading_session()
        if not in_session:
            tz = pytz.timezone(config.DISPLAY_TIMEZONE)
            local_now = datetime.now(pytz.utc).astimezone(tz)
            logger.warning(f"Trade rejected: Outside of allowed sessions. Current local time: {local_now.strftime('%H:%M')} {config.DISPLAY_TIMEZONE}")
            return False
        
        session_name = session_info['name']
        
        # If we hit the limit, update_from_history would have set trading_paused to True.
        # But we need to make sure we are still talking about the SAME session.
        if self.trading_paused and self.current_session == session_name:
            logger.warning(f"Trading is currently paused for the {session_name} session due to risk limits.")
            return False
        
        logger.info(f"Session check passed: Currently in {session_name} session.")

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
