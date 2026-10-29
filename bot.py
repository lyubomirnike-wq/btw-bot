import os, json, time, uuid, urllib.request
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
TZ = ZoneInfo("Europe/Berlin")

TOKEN = os.environ["TELEGRAM_TOKEN"]
CHAT_IDS = [c.strip() for c in os.environ["TELEGRAM_CHAT_ID"].split(",") if c.strip()]
STEP = 1000          # крок рівнів
STATE_FILE = "last_level.txt"
UA = {"User-Agent": "btc-bot"}
GRAN = 900           # свічка = 15 хвилин (дозволено: 300, 900, 3600, 21600)

def get_json(url):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.load(r)

def get_price():
    return float(get_json("https://api.coinbase.com/v2/prices/BTC-USD/spot")["data"]["amount"])

def get_candles():
    end = int(time.time())
    start = end - 24 * 3600
    iso = lambda t: datetime.fromtimestamp(t, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    url = ("https://api.exchange.coinbase.com/products/BTC-USD/candles"
           f"?granularity={GRAN}&start={iso(start)}&end={iso(end)}")
    return sorted(get_json(url), key=lambda c: c[0])

def make_chart(candles, price, pct, level=None, path="chart.png"):
    BG, PANEL, GRID, TXT = "#0b0e14", "#0f131b", "#1d2330", "#8b93a3"
    GREEN, RED = "#26a69a", "#ef5350"
    fig = plt.figure(figsize=(10, 6.4), dpi=140)
    fig.patch.set_facecolor(BG)
    gs = fig.add_gridspec(2, 1, height_ratios=[4.2, 1], hspace=0.04,
                          left=0.04, right=0.915, top=0.84, bottom=0.07)
    ax = fig.add_subplot(gs[0]); av = fig.add_subplot(gs[1], sharex=ax)
    for a in (ax, av):
        a.set_facecolor(PANEL)
        a.grid(color=GRID, linewidth=0.6)
        a.yaxis.tick_right()
        a.tick_params(colors=TXT, labelsize=9, length=0)
        for sp in a.spines.values(): sp.set_visible(False)
    xs = [mdates.date2num(datetime.fromtimestamp(c[0], tz=TZ)) for c in candles]
    width = 0.72 * (GRAN / 86400)
    lows = [c[1] for c in candles]; highs = [c[2] for c in candles]
    lo, hi = min(lows), max(highs)
    if level is not None:
        lo, hi = min(lo, level), max(hi, level)
    pad = (hi - lo) * 0.10
    # свічки + обсяг
    for x, c in zip(xs, candles):
        low, high, op, cl, vol = c[1], c[2], c[3], c[4], c[5]
        col = GREEN if cl >= op else RED
        ax.vlines(x, low, high, color=col, linewidth=1)
        ax.bar(x, max(abs(cl - op), 1), bottom=min(op, cl), width=width, color=col, linewidth=0)
        av.bar(x, vol, width=width, color=col, alpha=0.85, linewidth=0)
    ax.set_ylim(lo - pad, hi + pad)
    ax.set_xlim(xs[0] - width * 2, xs[-1] + width * 6)
    # круглі рівні 1000
    lvl = int((lo - pad) // STEP * STEP)
    while lvl <= hi + pad:
        if lo - pad <= lvl <= hi + pad:
            ax.axhline(lvl, color="#2c3446", linewidth=0.9, linestyle=(0, (4, 4)), zorder=0)
        lvl += STEP
    # виділений рівень, про який сповіщення
    if level is not None:
        ax.axhline(level, color="#f5c542", linewidth=1.6, zorder=1)
        ax.text(0.006, level, f" ${level:,} ", transform=ax.get_yaxis_transform(), va="bottom", ha="left",
                color="#0b0e14", fontsize=9.5, fontweight="bold",
                bbox=dict(boxstyle="round,pad=0.2", fc="#f5c542", ec="none"))
    # макс/мін за добу
    ih = highs.index(hi); il = lows.index(lo)
    ax.annotate(f"${hi:,.0f}", (xs[ih], hi), xytext=(0, 6), textcoords="offset points",
                ha="center", color=TXT, fontsize=8.5)
    ax.annotate(f"${lo:,.0f}", (xs[il], lo), xytext=(0, -13), textcoords="offset points",
                ha="center", color=TXT, fontsize=8.5)
    # мітка поточної ціни
    pc = GREEN if pct >= 0 else RED
    ax.axhline(price, color=pc, linewidth=0.9, linestyle=(0, (2, 2)))
    ax.text(1.004, price, f"${price:,.0f}", transform=ax.get_yaxis_transform(), va="center", ha="left",
            color="white", fontsize=9, fontweight="bold",
            bbox=dict(boxstyle="round,pad=0.25", fc=pc, ec="none"))
    ax.yaxis.set_major_formatter(lambda v, _: f"${v:,.0f}")
    plt.setp(ax.get_xticklabels(), visible=False)
    av.yaxis.set_major_formatter(lambda v, _: f"{v:,.0f}")
    av.xaxis_date(tz=TZ)
    av.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M", tz=TZ))
    av.set_ylim(0, max(c[5] for c in candles) * 1.15)
    av.set_yticks([])
    av.text(0.005, 0.86, "Обсяг", transform=av.transAxes, color=TXT, fontsize=8.5, va="top")
    # шапка
    fig.text(0.04, 0.935, "BTC / USD", color=TXT, fontsize=13, va="center")
    fig.text(0.04, 0.875, f"${price:,.0f}", color="white", fontsize=27, fontweight="bold", va="center")
    fig.text(0.915, 0.905, f"{pct:+.2f}%", color=pc, fontsize=27, fontweight="bold", va="center", ha="right")
    fig.text(0.915, 0.953, "за 24 год", color=TXT, fontsize=10, ha="right", va="center")
    fig.savefig(path, facecolor=fig.get_facecolor())
    plt.close(fig)
    return path

def multipart(fields, filename, filedata):
    b = uuid.uuid4().hex
    body = b""
    for k, v in fields.items():
        body += (f"--{b}\r\nContent-Disposition: form-data; name=\"{k}\"\r\n\r\n{v}\r\n").encode()
    body += (f"--{b}\r\nContent-Disposition: form-data; name=\"photo\"; filename=\"{filename}\"\r\n"
             "Content-Type: image/png\r\n\r\n").encode() + filedata + b"\r\n"
    body += f"--{b}--\r\n".encode()
    return body, f"multipart/form-data; boundary={b}"

def send_photo(path, caption):
    data = open(path, "rb").read()
    for chat in CHAT_IDS:
        try:
            body, ctype = multipart({"chat_id": chat, "caption": caption}, "chart.png", data)
            req = urllib.request.Request(f"https://api.telegram.org/bot{TOKEN}/sendPhoto",
                                         data=body, headers={"Content-Type": ctype})
            urllib.request.urlopen(req, timeout=40)
        except Exception as e:
            print("не вдалось надіслати в", chat, e)

def report(text, price, level=None):
    candles = get_candles()
    pct = (price - candles[0][3]) / candles[0][3] * 100
    caption = f"{text}\nЗараз: ${price:,.0f}\n24 год: {pct:+.2f}%"
    send_photo(make_chart(candles, price, pct, level), caption)

def decide(anchor, price):
    """anchor = останній рівень. Сповіщення лише коли ціна дійшла до anchor+STEP або anchor-STEP."""
    if price >= anchor + STEP:
        n = int(price // STEP * STEP)
        return n, f"🟢 BTC досяг ${n:,}", n
    if price <= anchor - STEP:
        n = int(-(-price // STEP) * STEP)
        return n, f"🔴 BTC впав до ${n:,}", n
    return anchor, None, None

def load_anchor():
    try:
        return int(open(STATE_FILE).read().split()[0]) // STEP * STEP
    except Exception:
        return None

if __name__ == "__main__":
    price = get_price()
    anchor = load_anchor()
    if anchor is None:
        anchor = int(round(price / STEP) * STEP)
        report("✅ Бот запущено", price, anchor)
    else:
        anchor, text, level = decide(anchor, price)
        if text:
            report(text, price, level)
    open(STATE_FILE, "w").write(str(anchor))
