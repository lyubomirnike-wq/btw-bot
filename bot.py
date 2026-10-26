import os, json, urllib.request

TOKEN = os.environ["TELEGRAM_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]
STEP = 1000
STATE_FILE = "last_level.txt"

def get_price():
    url = "https://api.coinbase.com/v2/prices/BTC-USD/spot"
    with urllib.request.urlopen(url, timeout=20) as r:
        return float(json.load(r)["data"]["amount"])

def send(text):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    data = json.dumps({"chat_id": CHAT_ID, "text": text}).encode()
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    urllib.request.urlopen(req, timeout=20)

price = get_price()
level = int(price // STEP * STEP)

try:
    last = int(open(STATE_FILE).read().strip())
except Exception:
    last = None

if last is None:
    send(f"✅ Бот запущено. BTC зараз ${price:,.0f}")
elif level > last:
    send(f"🟢 BTC перетнув ${level:,} вгору\nЗараз: ${price:,.0f}")
elif level < last:
    send(f"🔴 BTC впав нижче ${last:,}\nЗараз: ${price:,.0f}")

open(STATE_FILE, "w").write(str(level))
