import unittest

from telegram.parser import parse_signal


class FixedStopLossParserTests(unittest.TestCase):
    def test_sell_uses_70_pips_above_entry_and_ignores_telegram_sl(self):
        signal = parse_signal(
            "SELL XAUUSD 4276-4280\nTP 4272\nSL 9999"
        )

        self.assertIsNotNone(signal)
        self.assertEqual(signal["entry"], 4278.0)
        self.assertEqual(signal["sl"], 4278.7)

    def test_buy_uses_70_pips_below_entry_without_sl_line(self):
        signal = parse_signal(
            "BUY XAUUSD 4008-4004\nTP 4012"
        )

        self.assertIsNotNone(signal)
        self.assertEqual(signal["entry"], 4006.0)
        self.assertEqual(signal["sl"], 4005.3)


if __name__ == "__main__":
    unittest.main()
