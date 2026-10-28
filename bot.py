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
STATE_FILE = "last_level.txt"
UA = {"User-Agent": "btc-bot"}

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
           f"?granularity=900&start={start}&end={end}")
    return sorted(get_json(url), key=lambda c: c[0])

def make_chart(candles, price, path="chart.png"):
    t = [datetime.fromtimestamp(c[0], tz=TZ) for c in candles]
    closes = [c[4] for c in candles]
    up = closes[-1] >= closes[0]
    color = "#16c784" if up else "#ea3943"
    fig, ax = plt.subplots(figsize=(8, 4.5), dpi=150)
    fig.patch.set_facecolor("#0e1117"); ax.set_facecolor("#0e1117")
    ax.plot(t, closes, color=color, linewidth=2)
    ax.fill_between(t, closes, min(closes), color=color, alpha=0.15)
    ax.set_ylim(min(closes) * 0.998, max(closes) * 1.002)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M", tz=TZ))
    ax.tick_params(colors="#9aa0a6")
    ax.yaxis.set_major_formatter(lambda v, _: f"${v:,.0f}")
    for s in ax.spines.values(): s.set_visible(False)
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
nearest = int(round(price / STEP) * STEP)

try:
    anchor = int(open(STATE_FILE).read().strip())
except Exception:
    anchor = None

if anchor is None:
    report("✅", price)
    anchor = nearest
elif price >= anchor + STEP:
    anchor = int(price // STEP * STEP)
    report("🟢", price)
elif price <= anchor - STEP:
    anchor = int(-(-price // STEP) * STEP)
    report("🔴", price)

open(STATE_FILE, "w").write(str(anchor))
