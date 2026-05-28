# MT5 Telegram Trading Bot

## Setup Instructions

### 1. Prerequisites
- Python 3.9+
- A MetaTrader 5 terminal installed on your Windows machine.
- A Telegram account.

### 2. Installation
   Install dependencies:
   ```cmd
   pip install -r requirements.txt
   ```

### 3. Running the Bot
Make sure your MT5 terminal is open and logged into the correct account (even if the bot handles login natively, having the terminal open ensures background services are active).

Run the bot:
```cmd
.venv\Scripts\python main.py
py main.py
```
*Note: On first run, Telethon will ask for a verification code sent to your Telegram app. Enter the code in the terminal.*

Run the script for csv upload:
```cmd
& E:\Python\trading-bot\.venv\Scripts\python.exe E:\Python\trading-bot\upload_trades.py
```

### 4. Stopping the Bot
To instantly stop the bot (Kill Switch), simply press `Ctrl + C` in the terminal.
