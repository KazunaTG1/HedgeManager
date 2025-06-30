import os, requests, pandas as pd
from IPython.display import display, clear_output
import math
import yfinance as yf
from matplotlib import pyplot as plt
import schedule
import time
import platform
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
from colorama import init, Fore, Style
import customtkinter as ctk


os.environ["TRADIER_TOKEN"] = "tiEeBvbQhxYsfxEkp9CYKPnsGP4E"
TOKEN = os.environ["TRADIER_TOKEN"]
BASE = "https://api.tradier.com/"
HEADERS = { "Authorization": f"Bearer {TOKEN}", "Accept": "application/json" }

def tradier(path, params=None, verb="GET", data=None):
    url = BASE + path.lstrip("/")
    r = requests.request(verb, url, headers=HEADERS, params=params, data=data, timeout=10)
    if r.status_code != 200:
        raise RuntimeError(f"HTTP {r.status_code}: {r.text[:300]} ...")
    if "application/json" not in r.headers.get("Content-Type", ""):
        raise RuntimeError(f"Unexpected content-type: {r.headers.get('Content-Type')}:\n {r.text[:300]} ...")
    return r.json()

def get_last_price(symbol):
    js = tradier("v1/markets/quotes", params={"symbols": symbol})
    quotes = js["quotes"]["quote"]
    return quotes['last']

def get_chain(symbol, expiration, option_type="call"):
    chain = tradier("v1/markets/options/chains", params={"symbol": symbol, "expiration": expiration, "greeks": True})
    return chain["options"]["option"]

def get_contract(symbol, expiration, strike, opt_type="call"):
    js = tradier("v1/markets/options/chains", params={"symbol":symbol, "expiration": expiration, "strikes": strike, "greeks": True})
    for c in js["options"]["option"]:
        if c["option_type"] == opt_type and c["strike"] == strike:
            return c
    return None

total_wait_time_sec = 300

refresh_div = 30.0
refresh_rate = total_wait_time_sec / refresh_div

opQQQ = { "Ticker": "QQQ", "Expiration": "2025-07-03", "Strikes": { "Call": 550, "Put": 525 } }
opSPY = { "Ticker": "SPY", "Expiration": "2025-07-03", "Strikes": { "Call": 620, "Put": 610} }

def get_positions(option):
    call = get_contract(option["Ticker"], option["Expiration"], option["Strikes"]["Call"], "call")
    put = get_contract(option["Ticker"], option["Expiration"], option["Strikes"]["Put"], "put")
    return call, put

def get_position_delta(call, put, st_delta):

    time_str = call["greeks"]["updated_at"]
    dt_utc = datetime.strptime(time_str, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
    local_dt = dt_utc.astimezone(ZoneInfo("America/New_York")).strftime("%Y-%m-%d %H:%M:%S")
    c_delta, p_delta = call["greeks"]["delta"], put["greeks"]["delta"]
    option_delta = c_delta + p_delta
    net_delta = (option_delta * 100) - st_delta
    rehedge_alert = abs(net_delta) > threshold
    return c_delta, p_delta, option_delta, net_delta, local_dt, rehedge_alert

threshold = 5

ctk.set_appearance_mode("System")
ctk.set_default_color_theme("blue")

# Create main window
app = ctk.CTk()
app.title("Delta Hedge Manager")
app.geometry("600x900")

# Header label
header = ctk.CTkLabel(app, text="Delta Hedge Manager", font=("Arial", 32, "bold"))
header.pack(pady=30)

# Entry fields

ticker_entry = ctk.CTkEntry(app, width=300, placeholder_text=f'Stock Ticker...')
ticker_entry.pack(pady=5)

expiration_entry = ctk.CTkEntry(app, width=300, placeholder_text=f'Expiration Date (YYYY-MM-DD)...')
expiration_entry.pack(pady=5)

strike_entry = ctk.CTkEntry(app, width=300, placeholder_text=f'Strike Price...')
strike_entry.pack(pady=5)

shares_entry = ctk.CTkEntry(app, width=300, placeholder_text=f"Shares... ")
shares_entry.pack(pady=5)

threshold_entry = ctk.CTkEntry(app, width=300, placeholder_text=f"Threshold:")
threshold_entry.pack(pady=5)

refresh_entry = ctk.CTkEntry(app, width=300, placeholder_text=f"Refresh rate (mins):")
refresh_entry.pack(pady=5)
LOCAL_TZ = ZoneInfo("America/New_York")
min_per_refresh = 5
ms_per_refresh = min_per_refresh * 60000
def seconds_until_next_quarter_hour(tz=LOCAL_TZ) -> float:
    now = datetime.now(tz)
    target = now.replace(minute=15, second=0, microsecond=0)
    if now >= target:
        target += timedelta(hours=1)
    return (target - now).total_seconds()
def schedule_next_update():
    delay_ms = int(seconds_until_next_quarter_hour() * 1000)
    app.after(delay_ms, update)
def update():
    print(f"Refreshed: {datetime.now(LOCAL_TZ).strftime('%Y-%m-%d %H:%M:%S')}")

    display()
    schedule_next_update()
def start():
    thresh = float(threshold_entry.get())
    threshold_lbl.configure(text=f"Threshold: ${thresh:.2f}")
    refresh = float(refresh_entry.get())
    ms_per_refresh = int(refresh * 60000)
    refresh_lbl.configure(text=f"Refresh Rate: {refresh:.2f} min(s)")
    if len(shares_entry.get()) > 0:
        display()
        schedule_next_update()

def display():
    print("Updating...")
    spy_st_delta = float(shares_entry.get())
    display_option(opSPY, spy_st_delta, spy_header, spy_label, spy_alert_lbl)
# Output label

def display_option(option, st_delta, header_lbl, label, alert_lbl):
    call, put = get_positions(option)
    call_price = float(call["last"])
    put_price = float(put['last'])
    c_delta, p_delta, option_delta, net_delta, update_dt, rehedge_alert = get_position_delta(call, put, st_delta)
    txt_net = f"Net Δ: ${net_delta:.2f}"
    txt_st = f"Stock Δ: ${st_delta:.2f}"
    txt_call = f"Call Δ: ${c_delta*100:.2f}"
    txt_put = f"Put Δ: ${p_delta*100:.2f}"
    txt_op = f"Option Δ: ${option_delta*100:.2f}"
    dt_lbl.configure(text=f'Last Updated: {update_dt}')
    header_lbl.configure(text=f"{call['symbol']} / {put['symbol']}")
    label.configure(text=f"{txt_call}\n{txt_put}\n{txt_op}\n\n{txt_st}\n\n{txt_net}")
    alert_color = "white"
    if rehedge_alert == True:
        alert_color = "red"
    alert_lbl.configure(text=f"Rehedge: {rehedge_alert}", text_color=alert_color)

dt_lbl = ctk.CTkLabel(app, text="", font=("Arial", 18, "bold"))
dt_lbl.pack(pady=3)

threshold_lbl = ctk.CTkLabel(app, text="", font=("Arial", 16))
threshold_lbl.pack(pady=3)

refresh_lbl = ctk.CTkLabel(app, text="", font=("Arial", 16))
refresh_lbl.pack(pady=3)

spy_header = ctk.CTkLabel(app, text="", font=("Arial", 24, "bold"))
spy_header.pack(pady=10)

spy_label = ctk.CTkLabel(app, text="", font=("Arial", 16))
spy_label.pack(pady=10)

spy_alert_lbl = ctk.CTkLabel(app, text="", font=("Arial", 18, "bold"))
spy_alert_lbl.pack(pady=10)

qqq_header = ctk.CTkLabel(app, text="", font=("Arial", 24, "bold"))
qqq_header.pack(pady=10)

qqq_label = ctk.CTkLabel(app, text="", font=("Arial", 16))
qqq_label.pack(pady=10)

qqq_alert_lbl = ctk.CTkLabel(app, text="", font=("Arial", 18, "bold"))
qqq_alert_lbl.pack(pady=10)

button = ctk.CTkButton(app, text="Start", command=start)
button.pack(pady=20)

# Start app
app.mainloop()
