# Stock Alert System — Setup Guide

## What This Does
- Scrapes live stock data (price, analyst targets, P/E, EV/EBITDA) from Yahoo Finance
- Calculates upside/downside % vs analyst consensus targets
- Flags over/under-valued stocks vs their sector median
- Sends a formatted HTML email summary with all triggered alerts

---

## Quick Start

### 1. Install Dependencies
```bash
pip install yfinance schedule pandas
```

### 2. Configure `stock_alerts.py`
Open the file and edit the **CONFIG** section at the top:

```python
CONFIG = {
    "watchlist": ["AAPL", "MSFT", "NVDA", ...],  # Your tickers

    # Alert thresholds
    "upside_threshold_pct": 15.0,     # Alert if upside to target >= 15%
    "downside_threshold_pct": -10.0,  # Alert if overpriced vs target

    # Email
    "email": {
        "enabled": True,
        "sender_email": "your@gmail.com",
        "sender_password": "xxxx xxxx xxxx xxxx",  # Gmail App Password
        "recipient_email": "you@gmail.com"
    }
}
```

### 3. Gmail App Password Setup
1. Go to myaccount.google.com → Security → 2-Step Verification → App Passwords
2. Create a new App Password (select "Mail")
3. Paste the 16-character password into `sender_password`

### 4. Run It

**Single check:**
```bash
python stock_alerts.py --run-once
```

**Recurring (every 6 hours):**
```bash
python stock_alerts.py --schedule
```

---

## Alert Types

| Alert | Trigger |
|-------|---------|
| 🟢 UPSIDE | Stock price ≥15% below analyst consensus target |
| 🔴 DOWNSIDE | Stock price ≥10% above analyst consensus target |
| ⚠️ P/E OVERVALUED | Stock P/E is 30%+ above sector median |
| 💡 P/E VALUE | Stock P/E is 20%+ below sector median |
| ⚠️ EV/EBITDA HIGH | EV/EBITDA is 25%+ above sector median |
| 💡 EV/EBITDA LOW | EV/EBITDA is 20%+ below sector median |

---

## Files
- `stock_alerts.py` — Main Python backend (data scraping + email alerts)
- `dashboard.jsx` — React dashboard for visual monitoring
- `alerts_output.json` — Auto-generated after each run with full results

---

## Disclaimer
This tool is for informational purposes only and does not constitute financial advice.
Data sourced from Yahoo Finance via the `yfinance` library.
# stockinfo
