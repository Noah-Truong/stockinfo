#!/usr/bin/env python3
"""
Stock Alert System
==================
Scrapes stock data from Yahoo Finance (as a proxy for FactSet/S&P IQ metrics),
calculates upside/downside vs analyst price targets, flags valuation anomalies
(P/E, EV/EBITDA vs sector medians), and sends email alerts.

Requirements:
    pip install yfinance requests pandas smtplib schedule

Usage:
    1. Configure settings in the CONFIG section below.
    2. Run once:       python stock_alerts.py --run-once
    3. Run on schedule: python stock_alerts.py --schedule   (checks every 6 hours)
"""

import os
import requests
import pandas as pd
import smtplib
import json
import argparse
import schedule
import time
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime

# ─────────────────────────────────────────────
#  CONFIG — Edit these before running
# ─────────────────────────────────────────────
CONFIG = {
    # Your stock watchlist (tickers)
    "watchlist": [
        "AAPL", "MSFT", "GOOGL", "AMZN", "META",
        "NVDA", "JPM", "BAC", "XOM", "JNJ"
    ],

    # Alert thresholds
    "upside_threshold_pct": 15.0,       # Alert if upside to target >= 15%
    "downside_threshold_pct": -10.0,    # Alert if downside to target <= -10%
    "pe_premium_pct": 30.0,             # Alert if stock P/E is 30%+ above sector median
    "pe_discount_pct": -20.0,           # Alert if stock P/E is 20%+ below sector median
    "evebitda_premium_pct": 25.0,       # Alert if EV/EBITDA is 25%+ above sector median
    "evebitda_discount_pct": -20.0,     # Alert if EV/EBITDA is 20%+ below sector median

    # Email settings
    # Credentials are read from environment variables when running on GitHub Actions.
    # When running locally, you can either set those env vars OR replace the fallback strings.
    "email": {
        "enabled": True,
        "smtp_server": "smtp.gmail.com",        # Change for Outlook: smtp.office365.com
        "smtp_port": 587,
        "sender_email":    os.environ.get("SENDER_EMAIL",    "your_email@gmail.com"),
        "sender_password": os.environ.get("SENDER_PASSWORD", "your_app_password"),
        "recipient_email": os.environ.get("RECIPIENT_EMAIL", "your_email@gmail.com"),
    },

    # Schedule (hours between checks when using --schedule)
    "check_interval_hours": 6,

    # Output alerts to a JSON file as well
    "save_alerts_json": True,
    "alerts_output_file": "alerts_output.json"
}

# Sector median P/E and EV/EBITDA benchmarks (approximations; update as needed)
# Source: Typical market averages by GICS sector
SECTOR_BENCHMARKS = {
    "Technology":              {"pe": 28.0, "ev_ebitda": 20.0},
    "Communication Services":  {"pe": 22.0, "ev_ebitda": 14.0},
    "Consumer Cyclical":       {"pe": 24.0, "ev_ebitda": 13.0},
    "Consumer Defensive":      {"pe": 20.0, "ev_ebitda": 13.0},
    "Healthcare":              {"pe": 22.0, "ev_ebitda": 14.0},
    "Financial Services":      {"pe": 14.0, "ev_ebitda": 10.0},
    "Energy":                  {"pe": 12.0, "ev_ebitda": 7.0},
    "Industrials":             {"pe": 20.0, "ev_ebitda": 13.0},
    "Basic Materials":         {"pe": 15.0, "ev_ebitda": 9.0},
    "Real Estate":             {"pe": 35.0, "ev_ebitda": 18.0},
    "Utilities":               {"pe": 18.0, "ev_ebitda": 11.0},
    "Default":                 {"pe": 20.0, "ev_ebitda": 13.0},
}

# ─────────────────────────────────────────────
#  LOGGING
# ─────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("stock_alerts.log")
    ]
)
log = logging.getLogger(__name__)


# ─────────────────────────────────────────────
#  DATA FETCHING (FactSet)
# ─────────────────────────────────────────────
FACTSET_BASE_URL = os.environ.get("FACTSET_BASE_URL", "https://api.factset.com")
# Set these to the exact paths from the FactSet Prices / Fundamentals API docs
FACTSET_PRICES_PATH = os.environ.get("FACTSET_PRICES_PATH", "/content/prices/v2/prices")
FACTSET_FUNDAMENTALS_PATH = os.environ.get("FACTSET_FUNDAMENTALS_PATH", "/content/fundamentals/v1/fundamentals")
FACTSET_API_KEY = os.environ.get("FACTSET_API_KEY")
FACTSET_API_SECRET = os.environ.get("FACTSET_API_SECRET")

# Comma-separated list of metric codes for the Fundamentals API, e.g.
# "FF_PX_TARGET_MEAN,FF_PX_TARGET_HIGH,FF_PX_TARGET_LOW,FF_PE_TRAIL,FF_EV_EBITDA"
FACTSET_FUNDAMENTALS_METRICS = os.environ.get(
    "FACTSET_FUNDAMENTALS_METRICS",
    "FF_PX_TARGET_MEAN,FF_PX_TARGET_HIGH,FF_PX_TARGET_LOW,FF_PE_TRAIL,FF_EV_EBITDA",
).split(",")


def _factset_request(method: str, path: str, *, params: dict | None = None, json_body: dict | None = None) -> dict:
    """
    Helper to call a FactSet REST endpoint using basic auth.
    Supports both GET (with query params) and POST (with JSON body), matching the
    patterns from the official Prices and Fundamentals API examples.
    """
    url = f"{FACTSET_BASE_URL}{path}"
    auth = (FACTSET_API_KEY, FACTSET_API_SECRET) if FACTSET_API_KEY and FACTSET_API_SECRET else None
    resp = requests.request(method, url, params=params, json=json_body, auth=auth, timeout=20)
    resp.raise_for_status()
    return resp.json()


def fetch_stock_data(ticker: str) -> dict:
    """
    Fetch key metrics for a ticker using FactSet Prices + Fundamentals APIs.

    This follows the request/response patterns from:
      - Prices API:  data[ { fsymId, date, price, requestId, ... } ]
      - Fundamentals API: data[ { requestId, metric, value, ... }, ... ]
    """
    try:
        # Most FactSet equity ids are of the form "TICKER-COUNTRYCODE"
        fid = f"{ticker}-US"

        # 1) Prices API — POST body with ids[], date range, etc.
        prices_body = {
            "ids": [fid],
            "startDate": datetime.now().strftime("%Y-%m-%d"),
            "endDate": datetime.now().strftime("%Y-%m-%d"),
            "frequency": "D",
            "calendar": "FIVEDAY",
            "currency": "LOCAL",
            "adjust": "SPLIT",
        }
        prices_json = _factset_request("POST", FACTSET_PRICES_PATH, json_body=prices_body)
        prices_data = prices_json.get("data") or []

        # Take the last record for this id if multiple rows are returned
        price_item = next(
            (row for row in reversed(prices_data) if row.get("requestId") == fid or row.get("requestId") == ticker),
            (prices_data[-1] if prices_data else {}),
        )

        # 2) Fundamentals API — POST body with ids[], metrics[], etc.
        fundamentals_body = {
            "data": {
                "ids": [fid],
                "periodicity": "ANN",
                "metrics": FACTSET_FUNDAMENTALS_METRICS,
                "currency": "USD",
                "updateType": "RP",
            }
        }
        fundamentals_json = _factset_request("POST", FACTSET_FUNDAMENTALS_PATH, json_body=fundamentals_body)
        fundamentals_data = fundamentals_json.get("data") or []

        # Convert list of {metric, value, ...} into a simple dict: metric -> latest value
        metric_values: dict[str, float] = {}
        for row in fundamentals_data:
            m = row.get("metric")
            v = row.get("value")
            if m is not None and v is not None:
                metric_values[m] = v

        # Map specific metrics — adjust metric codes as needed for your account
        metrics = {m.strip(): metric_values.get(m.strip()) for m in FACTSET_FUNDAMENTALS_METRICS}

        current_price = price_item.get("price")
        # Placeholder mappings; update these metric codes to the ones that correspond
        # to analyst targets and valuation ratios in your FactSet setup.
        target_mean = metrics.get("FF_PX_TARGET_MEAN")
        target_high = metrics.get("FF_PX_TARGET_HIGH")
        target_low = metrics.get("FF_PX_TARGET_LOW")
        pe_ratio = metrics.get("FF_PE_TRAIL")
        ev_ebitda = metrics.get("FF_EV_EBITDA")

        sector = price_item.get("sector") or "Default"
        name = price_item.get("name") or price_item.get("requestId") or ticker
        recommendation = "N/A"
        num_analysts = 0
        market_cap = price_item.get("marketCap")

        return {
            "ticker":         ticker,
            "name":           name,
            "sector":         sector,
            "current_price":  current_price,
            "target_mean":    target_mean,
            "target_high":    target_high,
            "target_low":     target_low,
            "pe_ratio":       pe_ratio,
            "ev_ebitda":      ev_ebitda,
            "recommendation": recommendation,
            "num_analysts":   num_analysts,
            "market_cap":     market_cap,
            "error":          None,
        }
    except Exception as e:
        log.warning(f"Failed to fetch data for {ticker} from FactSet: {e}")
        return {"ticker": ticker, "error": str(e)}


# ─────────────────────────────────────────────
#  ALERT LOGIC
# ─────────────────────────────────────────────
def calculate_alerts(data: dict) -> list:
    """Return a list of alert dicts for a given stock data record."""
    if data.get("error"):
        return []

    alerts = []
    ticker = data["ticker"]
    name   = data["name"]
    sector = data.get("sector", "Default")
    benchmarks = SECTOR_BENCHMARKS.get(sector, SECTOR_BENCHMARKS["Default"])

    # ── 1. Price vs Analyst Target ───────────────
    price  = data.get("current_price")
    target = data.get("target_mean")

    if price and target and price > 0:
        upside_pct = ((target - price) / price) * 100

        if upside_pct >= CONFIG["upside_threshold_pct"]:
            alerts.append({
                "ticker":    ticker,
                "name":      name,
                "type":      "UPSIDE",
                "severity":  "BUY SIGNAL 🟢",
                "message":   (
                    f"{name} ({ticker}) has {upside_pct:.1f}% upside to analyst consensus target.\n"
                    f"  Current Price : ${price:.2f}\n"
                    f"  Mean Target   : ${target:.2f}  |  High: ${data.get('target_high', 'N/A')}  |  Low: ${data.get('target_low', 'N/A')}\n"
                    f"  Consensus     : {data['recommendation']}  ({data['num_analysts']} analysts)"
                ),
                "upside_pct": round(upside_pct, 2)
            })

        elif upside_pct <= CONFIG["downside_threshold_pct"]:
            alerts.append({
                "ticker":    ticker,
                "name":      name,
                "type":      "DOWNSIDE",
                "severity":  "CAUTION 🔴",
                "message":   (
                    f"{name} ({ticker}) is trading {abs(upside_pct):.1f}% ABOVE analyst consensus target.\n"
                    f"  Current Price : ${price:.2f}\n"
                    f"  Mean Target   : ${target:.2f}  |  High: ${data.get('target_high', 'N/A')}  |  Low: ${data.get('target_low', 'N/A')}\n"
                    f"  Consensus     : {data['recommendation']}  ({data['num_analysts']} analysts)"
                ),
                "upside_pct": round(upside_pct, 2)
            })

    # ── 2. P/E Valuation Alert ───────────────────
    pe = data.get("pe_ratio")
    sector_pe = benchmarks["pe"]

    if pe and pe > 0 and sector_pe:
        pe_diff_pct = ((pe - sector_pe) / sector_pe) * 100

        if pe_diff_pct >= CONFIG["pe_premium_pct"]:
            alerts.append({
                "ticker":   ticker,
                "name":     name,
                "type":     "VALUATION_PE_PREMIUM",
                "severity": "OVERVALUED ⚠️",
                "message":  (
                    f"{name} ({ticker}) P/E is {pe_diff_pct:.1f}% ABOVE {sector} sector median.\n"
                    f"  Stock P/E     : {pe:.1f}x\n"
                    f"  Sector Median : {sector_pe:.1f}x"
                ),
                "pe_diff_pct": round(pe_diff_pct, 2)
            })

        elif pe_diff_pct <= CONFIG["pe_discount_pct"]:
            alerts.append({
                "ticker":   ticker,
                "name":     name,
                "type":     "VALUATION_PE_DISCOUNT",
                "severity": "VALUE OPPORTUNITY 💡",
                "message":  (
                    f"{name} ({ticker}) P/E is {abs(pe_diff_pct):.1f}% BELOW {sector} sector median.\n"
                    f"  Stock P/E     : {pe:.1f}x\n"
                    f"  Sector Median : {sector_pe:.1f}x"
                ),
                "pe_diff_pct": round(pe_diff_pct, 2)
            })

    # ── 3. EV/EBITDA Valuation Alert ────────────
    ev_ebitda = data.get("ev_ebitda")
    sector_ev = benchmarks["ev_ebitda"]

    if ev_ebitda and ev_ebitda > 0 and sector_ev:
        ev_diff_pct = ((ev_ebitda - sector_ev) / sector_ev) * 100

        if ev_diff_pct >= CONFIG["evebitda_premium_pct"]:
            alerts.append({
                "ticker":      ticker,
                "name":        name,
                "type":        "VALUATION_EV_PREMIUM",
                "severity":    "OVERVALUED ⚠️",
                "message":     (
                    f"{name} ({ticker}) EV/EBITDA is {ev_diff_pct:.1f}% ABOVE {sector} sector median.\n"
                    f"  Stock EV/EBITDA : {ev_ebitda:.1f}x\n"
                    f"  Sector Median   : {sector_ev:.1f}x"
                ),
                "ev_diff_pct": round(ev_diff_pct, 2)
            })

        elif ev_diff_pct <= CONFIG["evebitda_discount_pct"]:
            alerts.append({
                "ticker":      ticker,
                "name":        name,
                "type":        "VALUATION_EV_DISCOUNT",
                "severity":    "VALUE OPPORTUNITY 💡",
                "message":     (
                    f"{name} ({ticker}) EV/EBITDA is {abs(ev_diff_pct):.1f}% BELOW {sector} sector median.\n"
                    f"  Stock EV/EBITDA : {ev_ebitda:.1f}x\n"
                    f"  Sector Median   : {sector_ev:.1f}x"
                ),
                "ev_diff_pct": round(ev_diff_pct, 2)
            })

    return alerts


# ─────────────────────────────────────────────
#  EMAIL
# ─────────────────────────────────────────────
def send_email(alerts: list, all_data: list):
    """Send an HTML email summarising all triggered alerts."""
    cfg = CONFIG["email"]
    if not cfg["enabled"]:
        log.info("Email disabled in config.")
        return

    now = datetime.now().strftime("%B %d, %Y at %H:%M")
    subject = f"📈 Stock Alert Report — {len(alerts)} signal(s) — {datetime.now().strftime('%b %d')}"

    # Build HTML body
    rows_alerts = ""
    for a in alerts:
        color = "#16a34a" if "UPSIDE" in a["type"] or "DISCOUNT" in a["type"] else "#dc2626"
        rows_alerts += f"""
        <tr>
          <td style="padding:10px;border-bottom:1px solid #1e293b;font-weight:700;color:#f8fafc">{a['ticker']}</td>
          <td style="padding:10px;border-bottom:1px solid #1e293b;color:#94a3b8">{a['name']}</td>
          <td style="padding:10px;border-bottom:1px solid #1e293b">
            <span style="background:{color}20;color:{color};padding:3px 8px;border-radius:4px;font-size:12px;font-weight:700">{a['severity']}</span>
          </td>
          <td style="padding:10px;border-bottom:1px solid #1e293b;color:#cbd5e1;font-size:13px;white-space:pre-line">{a['message']}</td>
        </tr>"""

    rows_watchlist = ""
    for d in all_data:
        if d.get("error"):
            continue
        price  = d.get("current_price")
        target = d.get("target_mean")
        upside = f"{((target - price) / price * 100):.1f}%" if price and target and price > 0 else "N/A"
        up_color = "#16a34a" if upside != "N/A" and float(upside.replace('%','')) > 0 else "#dc2626"
        price_str  = f"${price:.2f}"  if price  else "N/A"
        target_str = f"${target:.2f}" if target else "N/A"
        rows_watchlist += f"""
        <tr>
          <td style="padding:8px 10px;border-bottom:1px solid #1e293b;font-weight:700;color:#f8fafc">{d['ticker']}</td>
          <td style="padding:8px 10px;border-bottom:1px solid #1e293b;color:#94a3b8">{d.get('name','')}</td>
          <td style="padding:8px 10px;border-bottom:1px solid #1e293b;color:#e2e8f0">{price_str}</td>
          <td style="padding:8px 10px;border-bottom:1px solid #1e293b;color:#e2e8f0">{target_str}</td>
          <td style="padding:8px 10px;border-bottom:1px solid #1e293b;color:{up_color};font-weight:700">{upside}</td>
          <td style="padding:8px 10px;border-bottom:1px solid #1e293b;color:#94a3b8">{d.get('pe_ratio') and f"{d['pe_ratio']:.1f}x" or 'N/A'}</td>
          <td style="padding:8px 10px;border-bottom:1px solid #1e293b;color:#94a3b8">{d.get('ev_ebitda') and f"{d['ev_ebitda']:.1f}x" or 'N/A'}</td>
          <td style="padding:8px 10px;border-bottom:1px solid #1e293b;color:#94a3b8">{d.get('sector','')}</td>
        </tr>"""

    html = f"""
<!DOCTYPE html>
<html>
<body style="margin:0;padding:0;background:#0f172a;font-family:'Segoe UI',sans-serif;">
<div style="max-width:900px;margin:32px auto;background:#1e293b;border-radius:12px;overflow:hidden;box-shadow:0 20px 60px rgba(0,0,0,0.5)">

  <!-- Header -->
  <div style="background:linear-gradient(135deg,#1e3a5f,#0f172a);padding:32px 40px;border-bottom:1px solid #334155">
    <h1 style="margin:0;color:#f8fafc;font-size:24px;font-weight:800;letter-spacing:-0.5px">
      📊 Stock Alert Report
    </h1>
    <p style="margin:8px 0 0;color:#64748b;font-size:14px">{now} &nbsp;·&nbsp; {len(CONFIG['watchlist'])} stocks monitored &nbsp;·&nbsp; {len(alerts)} alert(s) triggered</p>
  </div>

  <!-- Alerts Section -->
  <div style="padding:32px 40px">
    <h2 style="margin:0 0 20px;color:#f8fafc;font-size:18px;font-weight:700">⚡ Triggered Alerts</h2>
    {"<p style='color:#64748b'>No alerts triggered with current thresholds.</p>" if not alerts else f'''
    <table style="width:100%;border-collapse:collapse;font-size:14px">
      <thead>
        <tr style="background:#0f172a">
          <th style="padding:10px;text-align:left;color:#64748b;font-weight:600;font-size:12px;text-transform:uppercase;letter-spacing:.05em">Ticker</th>
          <th style="padding:10px;text-align:left;color:#64748b;font-weight:600;font-size:12px;text-transform:uppercase;letter-spacing:.05em">Company</th>
          <th style="padding:10px;text-align:left;color:#64748b;font-weight:600;font-size:12px;text-transform:uppercase;letter-spacing:.05em">Signal</th>
          <th style="padding:10px;text-align:left;color:#64748b;font-weight:600;font-size:12px;text-transform:uppercase;letter-spacing:.05em">Details</th>
        </tr>
      </thead>
      <tbody>{rows_alerts}</tbody>
    </table>'''}
  </div>

  <!-- Watchlist Summary -->
  <div style="padding:0 40px 32px">
    <h2 style="margin:0 0 20px;color:#f8fafc;font-size:18px;font-weight:700">📋 Full Watchlist Snapshot</h2>
    <table style="width:100%;border-collapse:collapse;font-size:13px">
      <thead>
        <tr style="background:#0f172a">
          <th style="padding:8px 10px;text-align:left;color:#64748b;font-size:11px;text-transform:uppercase;letter-spacing:.05em">Ticker</th>
          <th style="padding:8px 10px;text-align:left;color:#64748b;font-size:11px;text-transform:uppercase;letter-spacing:.05em">Name</th>
          <th style="padding:8px 10px;text-align:left;color:#64748b;font-size:11px;text-transform:uppercase;letter-spacing:.05em">Price</th>
          <th style="padding:8px 10px;text-align:left;color:#64748b;font-size:11px;text-transform:uppercase;letter-spacing:.05em">Target</th>
          <th style="padding:8px 10px;text-align:left;color:#64748b;font-size:11px;text-transform:uppercase;letter-spacing:.05em">Upside</th>
          <th style="padding:8px 10px;text-align:left;color:#64748b;font-size:11px;text-transform:uppercase;letter-spacing:.05em">P/E</th>
          <th style="padding:8px 10px;text-align:left;color:#64748b;font-size:11px;text-transform:uppercase;letter-spacing:.05em">EV/EBITDA</th>
          <th style="padding:8px 10px;text-align:left;color:#64748b;font-size:11px;text-transform:uppercase;letter-spacing:.05em">Sector</th>
        </tr>
      </thead>
      <tbody>{rows_watchlist}</tbody>
    </table>
  </div>

  <!-- Footer -->
  <div style="padding:20px 40px;background:#0f172a;border-top:1px solid #1e293b">
    <p style="margin:0;color:#334155;font-size:12px">
      ⚠️ This report is for informational purposes only and does not constitute financial advice.
      Data sourced from FactSet. Always verify before making investment decisions.
    </p>
  </div>
</div>
</body>
</html>"""

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"]    = cfg["sender_email"]
        msg["To"]      = cfg["recipient_email"]
        msg.attach(MIMEText(html, "html"))

        with smtplib.SMTP(cfg["smtp_server"], cfg["smtp_port"]) as server:
            server.ehlo()
            server.starttls()
            server.login(cfg["sender_email"], cfg["sender_password"])
            server.sendmail(cfg["sender_email"], cfg["recipient_email"], msg.as_string())

        log.info(f"✅ Email sent to {cfg['recipient_email']}")
    except Exception as e:
        log.error(f"❌ Failed to send email: {e}")
        log.error("   → For Gmail: use an App Password (myaccount.google.com/apppasswords)")


# ─────────────────────────────────────────────
#  MAIN RUN
# ─────────────────────────────────────────────
def run_check():
    log.info("=" * 60)
    log.info(f"Running stock check for {len(CONFIG['watchlist'])} tickers...")
    log.info("=" * 60)

    all_data   = []
    all_alerts = []

    for ticker in CONFIG["watchlist"]:
        log.info(f"  Fetching {ticker}...")
        data = fetch_stock_data(ticker)
        all_data.append(data)

        if not data.get("error"):
            alerts = calculate_alerts(data)
            all_alerts.extend(alerts)
            if alerts:
                for a in alerts:
                    log.info(f"    🔔 {a['severity']} — {a['type']}")
            else:
                log.info(f"    ✓ No alerts")
        else:
            log.warning(f"    ⚠ Error: {data['error']}")

    log.info(f"\n{'─'*40}")
    log.info(f"Total alerts triggered: {len(all_alerts)}")

    # Save to JSON
    if CONFIG["save_alerts_json"]:
        output = {
            "run_time":   datetime.now().isoformat(),
            "alerts":     all_alerts,
            "watchlist":  [d for d in all_data if not d.get("error")]
        }
        with open(CONFIG["alerts_output_file"], "w") as f:
            json.dump(output, f, indent=2)
        log.info(f"Saved alerts to {CONFIG['alerts_output_file']}")

    # Send email
    send_email(all_alerts, all_data)

    return all_alerts, all_data


# ─────────────────────────────────────────────
#  ENTRY POINT
# ─────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Stock Alert System")
    parser.add_argument("--run-once", action="store_true", help="Run a single check and exit")
    parser.add_argument("--schedule", action="store_true", help="Run on a recurring schedule")
    args = parser.parse_args()

    if args.run_once or not args.schedule:
        run_check()
    elif args.schedule:
        interval = CONFIG["check_interval_hours"]
        log.info(f"Scheduling checks every {interval} hours. Press Ctrl+C to stop.")
        run_check()  # Run immediately on start
        schedule.every(interval).hours.do(run_check)
        while True:
            schedule.run_pending()
            time.sleep(60)