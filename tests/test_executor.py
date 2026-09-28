import unittest
from types import SimpleNamespace
from unittest.mock import patch

import MetaTrader5 as mt5

from trading import executor


class AllowTrading:
    def can_trade(self):
        return True


class ExecutorLimitOrderTests(unittest.TestCase):
    def setUp(self):
        self.signal = {
            "type": "SELL",
            "entry": 4278.0,  # midpoint of the 4276-4280 signal range
            "tp1": 4272.0,
            "sl": 9999.0,  # Telegram SL must be ignored.
        }
        self.result = SimpleNamespace(
            retcode=mt5.TRADE_RETCODE_DONE,
            comment="done",
            order=123,
        )

    @patch.object(executor.config, "SYMBOL", "XAUUSD")
    @patch.object(executor.config, "LOT_SIZE", 0.01)
    @patch.object(executor.config, "ORDER_EXPIRATION_MINUTES", None)
    @patch.object(executor.mt5, "symbol_select", return_value=True)
    @patch.object(executor.mt5, "symbol_info_tick")
    @patch.object(executor.mt5, "order_send")
    def test_range_signal_at_4272_submits_sell_limit_at_4278(
        self, order_send, symbol_info_tick, _symbol_select
    ):
        symbol_info_tick.return_value = SimpleNamespace(
            bid=4272.0,
            ask=4272.2,
            time=0,
        )
        order_send.return_value = self.result

        success = executor.execute_trade(self.signal, AllowTrading(), "Test")

        self.assertTrue(success)
        request = order_send.call_args.args[0]
        self.assertEqual(request["action"], mt5.TRADE_ACTION_PENDING)
        self.assertEqual(request["type"], mt5.ORDER_TYPE_SELL_LIMIT)
        self.assertEqual(request["price"], 4278.0)
        self.assertEqual(request["sl"], 4278.7)
        self.assertNotEqual(request["price"], 4272.0)

    @patch.object(executor.config, "SYMBOL", "XAUUSD")
    @patch.object(executor.config, "LOT_SIZE", 0.01)
    @patch.object(executor.config, "ORDER_EXPIRATION_MINUTES", None)
    @patch.object(executor.mt5, "symbol_select", return_value=True)
    @patch.object(executor.mt5, "symbol_info_tick")
    @patch.object(executor.mt5, "order_send")
    def test_buy_signal_below_entry_never_falls_back_to_market(
        self, order_send, symbol_info_tick, _symbol_select
    ):
        buy_signal = {
            "type": "BUY",
            "entry": 4278.0,
            "tp1": 4285.0,
            "sl": 4270.0,
        }
        symbol_info_tick.return_value = SimpleNamespace(
            bid=4271.8,
            ask=4272.0,
            time=0,
        )

        success = executor.execute_trade(buy_signal, AllowTrading(), "Test")

        self.assertFalse(success)
        order_send.assert_not_called()


if __name__ == "__main__":
    unittest.main()
