import os, requests, pandas as pd
from IPython.display import display, clear_output
import math
import yfinance as yf
from matplotlib import pyplot as plt
import time
import platform
from datetime import datetime
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

tckr = "QQQ"
expiry = "2025-07-03"

total_wait_time_sec = 300

refresh_div = 30.0
refresh_rate = total_wait_time_sec / refresh_div

opQQQ = { "Ticker": "QQQ", "Expiration": "2025-07-03", "Strikes": { "Call": 550, "Put": 525 } }
opSPY = { "Ticker": "SPY", "Expiration": "2025-06-30", "Strikes": { "Call": 617, "Put": 613} }

def get_positions(option):
    call = get_contract(option["Ticker"], option["Expiration"], option["Strikes"]["Call"], "call")
    put = get_contract(option["Ticker"], option["Expiration"], option["Strikes"]["Put"], "put")
    return call, put

def get_position_delta(call, put, st_delta):
    c_delta, p_delta = call["greeks"]["delta"], put["greeks"]["delta"]
    option_delta = c_delta + p_delta
    net_delta = option_delta * 100 - st_delta
    rehedge_alert = abs(net_delta) > threshold
    return c_delta, p_delta, option_delta, net_delta, rehedge_alert
def print_delta(option, call, put ,st_delta):
    c_delta, p_delta, option_delta, net_delta, rehedge_alert = get_position_delta(call, put, st_delta)
    print(f"{option['Ticker']} {option['Expiration']}: Strikes = Call {option['Strikes']['Call']}, Put {option['Strikes']['Put']}")
    print(f"Call Δ: ${c_delta*100:.4f}")
    print(f"Put Δ: ${p_delta*100:.4f}")
    print(f"Option Δ: ${option_delta*100:.4f}")
    print(f"Stock Δ: ${st_delta:.4f}")
    init()
    print(Fore.RED, f"Net Δ: ${net_delta:.4f}", Style.RESET_ALL)
    print("------- == Alerts == -------")
    if rehedge_alert:
        print(f"- Rehedge needed !!! \n  Net Δ ({net_delta:.4f}) > Threshold (±{threshold})")
    print("-------------------------------------")
    
threshold = 5
qqqStock = float(input(f"Current {opQQQ['Ticker']} shares: "))
spyStock = float(input(f"Current {opSPY['Ticker']} shares: "))
try:
    while True:
        now = datetime.now()
        spyCall, spyPut = get_positions(opSPY)
        qqqCall, qqqPut = get_positions(opQQQ)
        for i in range(0, int(refresh_div)):
            clear_output(wait=True)
            print("_______== Last Updated ==_______")
            print(now)
            print("_______== Options ==_______")
            print_delta(opSPY, spyCall, spyPut, spyStock)
            print_delta(opQQQ, qqqCall, qqqPut, qqqStock)
            print("_______== Time till Refresh ==________")
            progress = int(i // 5)
            prog_left = (int(refresh_div) // 5) - progress
            seconds_elapsed = (refresh_rate*i)
            perc_elapsed = seconds_elapsed / total_wait_time_sec
            print(f"{perc_elapsed*100:.2f}", "% " + "█" * progress + "|" * prog_left)
            print(f"{seconds_elapsed / 60:.2f} min / {total_wait_time_sec / 60.0:.2f} min")
            print(f"Refresh Rate: {refresh_rate:.2f} sec")
            time.sleep(refresh_rate-1) 
            
except KeyboardInterrupt:
    print("\nStopped by user.")

