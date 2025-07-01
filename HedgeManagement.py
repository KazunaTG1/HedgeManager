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
app.geometry("600x1000")

# Header label
header = ctk.CTkLabel(app, text="Delta Hedge Manager", font=("Arial", 32, "bold"))
header.pack(pady=30)

# Entry fields

ticker_entry = ctk.CTkEntry(app, width=300, placeholder_text=f'Stock Ticker...')
ticker_entry.pack(pady=5)

expiration_entry = ctk.CTkEntry(app, width=300, placeholder_text=f'Expiration Date (YYYY-MM-DD)...')
expiration_entry.pack(pady=5)

c_strike_entry = ctk.CTkEntry(app, width=300, placeholder_text=f'Call Strike Price...')
c_strike_entry.pack(pady=5)

p_strike_entry = ctk.CTkEntry(app, width=300, placeholder_text=f'Put Strike Price...')
p_strike_entry.pack(pady=5)

shares_entry = ctk.CTkEntry(app, width=300, placeholder_text=f"Shares... ")
shares_entry.pack(pady=5)
LOCAL_TZ = ZoneInfo("America/New_York")
options = []
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
    for opt in options:
        display_option(opt["spec"], opt["spec"]["Stock_Shares"], opt["header"], opt["body"], opt["alert"])
    schedule_next_update()
def start():
    thresh = float(threshold_entry.get())
    threshold_lbl.configure(text=f"Threshold: ${thresh:.2f}")
    update()
def add_option():
    try:
        spec = {
            "Ticker": ticker_entry.get(), 
            "Expiration": expiration_entry.get(), 
            "Strikes": { 
                "Call": float(c_strike_entry.get()), 
                "Put": float(p_strike_entry.get())},
            "Stock_Shares": float(shares_entry.get())}
    except ValueError:
        print("Enter numeric strikes")
    widget_bundle = make_option_widgets(app, spec)
    options.append(widget_bundle)
    update()
def make_option_widgets(parent, option_spec):
    header = ctk.CTkLabel(parent, font=("Arial", 24, "bold"))
    body = ctk.CTkLabel(parent, font=("Arial", 16))
    alert = ctk.CTkLabel(parent, font=("Arial", 18, "bold"))
    for w in (header, body, alert):
        w.pack(pady=6)
    return {"spec": option_spec, "header": header, "body": body, "alert": alert}
add_btn = ctk.CTkButton(app, text="Add Option", command=add_option)
add_btn.pack(pady=10)

button = ctk.CTkButton(app, text="Refresh", command=start)
button.pack(pady=10)

threshold_entry = ctk.CTkEntry(app, width=300, placeholder_text=f"Threshold:")
threshold_entry.pack(pady=5)




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



# Start app
app.mainloop()
