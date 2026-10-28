import os, json, time, uuid, urllib.request
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime
from zoneinfo import ZoneInfo
TZ = ZoneInfo("Europe/Berlin")

TOKEN = os.environ["TELEGRAM_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]
STEP = 1000
BUF = 150  # буфер проти спаму біля рівня
STATE_FILE = "last_level.txt"
UA = {"User-Agent": "btc-bot"}
GRAN = 1800  # свічка = 30 хвилин

def get_json(url):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.load(r)

def get_price():
    return float(get_json("https://api.coinbase.com/v2/prices/BTC-USD/spot")["data"]["amount"])

def get_candles():
    end = int(time.time())
    start = end - 24 * 3600
    url = ("https://api.exchange.coinbase.com/products/BTC-USD/candles"
           f"?granularity={GRAN}&start={start}&end={end}")
    return sorted(get_json(url), key=lambda c: c[0])

def make_chart(candles, price, path="chart.png"):
    GREEN, RED = "#16c784", "#ea3943"
    fig, ax = plt.subplots(figsize=(8, 4.5), dpi=150)
    fig.patch.set_facecolor("#0e1117"); ax.set_facecolor("#0e1117")
    width = 0.7 * (GRAN / 86400)
    for c in candles:
        x = mdates.date2num(datetime.fromtimestamp(c[0], tz=TZ))
        low, high, op, cl = c[1], c[2], c[3], c[4]
        col = GREEN if cl >= op else RED
        ax.vlines(x, low, high, color=col, linewidth=1)
        ax.bar(x, max(abs(cl - op), 1), bottom=min(op, cl), width=width, color=col, linewidth=0)
    lows = [c[1] for c in candles]; highs = [c[2] for c in candles]
    pad = (max(highs) - min(lows)) * 0.05
    ax.set_ylim(min(lows) - pad, max(highs) + pad)
    ax.set_xlim(mdates.date2num(datetime.fromtimestamp(candles[0][0], tz=TZ)) - width,
                mdates.date2num(datetime.fromtimestamp(candles[-1][0], tz=TZ)) + width * 4)
    ax.axhline(price, color="#9aa0a6", linewidth=0.8, linestyle="--")
    ax.xaxis_date(tz=TZ)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M", tz=TZ))
    ax.tick_params(colors="#9aa0a6")
    ax.yaxis.set_major_formatter(lambda v, _: f"${v:,.0f}")
    ax.yaxis.tick_right()
    for sp in ax.spines.values(): sp.set_visible(False)
    ax.grid(color="#2a2f3a", linewidth=0.6)
    ax.set_title(f"BTC/USD · 24 год · ${price:,.0f}", color="white", fontsize=14, loc="left")
    fig.tight_layout()
    fig.savefig(path, facecolor=fig.get_facecolor())
    plt.close(fig)
    return path

def send_photo(path, caption):
    b = uuid.uuid4().hex
    body = b""
    for k, v in (("chat_id", CHAT_ID), ("caption", caption)):
        body += (f"--{b}\r\nContent-Disposition: form-data; name=\"{k}\"\r\n\r\n{v}\r\n").encode()
    body += (f"--{b}\r\nContent-Disposition: form-data; name=\"photo\"; filename=\"chart.png\"\r\n"
             "Content-Type: image/png\r\n\r\n").encode() + open(path, "rb").read() + b"\r\n"
    body += f"--{b}--\r\n".encode()
    req = urllib.request.Request(f"https://api.telegram.org/bot{TOKEN}/sendPhoto", data=body,
                                 headers={"Content-Type": f"multipart/form-data; boundary={b}"})
    urllib.request.urlopen(req, timeout=40)

def report(emoji, price):
    candles = get_candles()
    first_open = candles[0][3]
    pct = (price - first_open) / first_open * 100
    caption = f"{emoji} BTC ${price:,.0f}\n24 год: {pct:+.2f}%"
    send_photo(make_chart(candles, price), caption)

price = get_price()
level = int(price // STEP * STEP)

try:
    anchor = int(open(STATE_FILE).read().strip()) // STEP * STEP
except Exception:
    anchor = None

if anchor is None:
    report("✅", price)
    anchor = level
elif price >= anchor + STEP + BUF:
    anchor = level
    report("🟢", price)
elif price <= anchor - BUF:
    anchor = level
    report("🔴", price)

open(STATE_FILE, "w").write(str(anchor))
