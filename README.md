# 📈 Superquote Tracker & Value Bet Bot

A fully automated Python tool designed to detect market inefficiencies in sports betting odds (Value Bets) in real-time. This project combines web scraping, API integration, and statistical analysis to track "Superquotes" on Bet365.

## 🚀 Key Features
* **Real-Time Monitoring:** Scrapes odds 24/7 using **Playwright** (handling dynamic SPAs content).
* **Instant Notifications:** Sends alerts via **Telegram Bot API** immediately when a value bet is detected.
* **Data Logging:** Automatically saves history to **Google Sheets** via API (`gspread`) for statistical analysis (ROI, EV).
* **Robustness:** Includes automatic error handling, exponential backoff retries, and heartbeat monitoring.

## 🛠️ Tech Stack
* **Language:** Python 3.x
* **Web Scraping:** Playwright (Async), Aiohttp
* **APIs:** Telegram Bot API, Google Sheets API
* **Logic:** Asyncio for concurrency, MD5 hashing for unique event tracking.

## ⚙️ Installation & Usage

1. **Clone the repo:**
   ```bash
   git clone [https://github.com/LorSt4r/superquote-tracker.git](https://github.com/LorSt4r/superquote-tracker.git)
Install dependencies:

Bash

pip install -r requirements.txt
playwright install
Configuration: Create a .env file in the root directory with your credentials:

Snippet di codice

TELEGRAM_BOT_TOKEN=your_token_here
TELEGRAM_CHAT_IDS=123456,789012
GOOGLE_SHEETS_CREDENTIALS_FILE=creds.json
Run:

Bash

python superquote_checker.py
⚠️ Disclaimer
This project was created for educational purposes to study statistical anomalies, web automation, and asynchronous programming.


###
