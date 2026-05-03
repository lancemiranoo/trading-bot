# MT5 Telegram Trading Bot

A robust, production-ready automated trading bot that listens to Telegram signals and executes them on MetaTrader 5 (MT5).

## Features

- **Real-Time Signal Parsing**: Listens to specified Telegram channels using Telethon and extracts BUY/SELL signals via Regex.
- **MT5 Integration**: Places LIMIT orders dynamically at the upper/lower bounds of a given entry zone.
- **Risk Management**:
  - Max open trades limit (Default: 5).
  - Daily loss limit (Default: $50).
  - Max consecutive losing trades (Default: 4).
- **Safety First**:
  - Paper Trading mode enabled by default.
  - Manual Kill Switch via KeyboardInterrupt (Ctrl+C).
  - Expiration of unfilled pending orders (Default: 10 mins).

## Setup Instructions

### 1. Prerequisites
- Python 3.9+
- A MetaTrader 5 terminal installed on your Windows machine.
- A Telegram account.

### 2. Installation
1. Navigate to the project directory:
   ```cmd
   cd e:\Python\trading-bot
   ```
2. Create and activate a virtual environment (optional but recommended):
   ```cmd
   python -m venv venv
   venv\Scripts\activate
   ```
3. Install dependencies:
   ```cmd
   pip install -r requirements.txt
   ```

### 3. Configuration
1. Go to [my.telegram.org](https://my.telegram.org) and create an App to get your `API_ID` and `API_HASH`.

2. Open `.env` and fill in your details:
   - Telegram `API_ID`, `API_HASH`, and `PHONE`.
   - `CHANNEL_IDS`: the IDs of the Telegram channels you want to listen to.
   - `MT5_LOGIN`, `MT5_PASSWORD`, and `MT5_SERVER`.
   - Ensure `PAPER_TRADING=True` while testing.

### 4. Running the Bot
Make sure your MT5 terminal is open and logged into the correct account (even if the bot handles login natively, having the terminal open ensures background services are active).

Run the bot:
```cmd
py main.py
```
*Note: On first run, Telethon will ask for a verification code sent to your Telegram app. Enter the code in the terminal.*

### 5. Stopping the Bot
To instantly stop the bot (Kill Switch), simply press `Ctrl + C` in the terminal.

## Architecture & Modules
- `config.py`: Environment variable and parameter loading.
- `main.py`: Entry point, orchestrates tasks and async loops.
- `signal_listener.py`: Connects to Telegram and parses new messages.
- `signal_parser.py`: Regex logic to extract signal components.
- `trade_executor.py`: Interacts with MT5 to place trades.
- `risk_manager.py`: Implements daily PnL and consecutive loss checks.
- `logger.py`: Centralized logging.