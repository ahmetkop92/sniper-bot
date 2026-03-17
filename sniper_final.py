$path = "$env:USERPROFILE\Desktop\sniper_final.py"

$code = @'
import json, time, urllib.request, urllib.parse

TOKEN = "8756453128:AAGrF-Thc7bMoxdDEg0ktnR96Xf-H-4qMAg"
CHAT_ID = "-5028102541"

# ===== SETTINGS =====
MIN_MCAP = 5_000_000
MAX_MCAP = 120_000_000
MIN_VOL = 700_000
MIN_VOL_MCAP_RATIO = 0.05
MAX_RESULTS = 5
SLEEP_SECONDS = 1800  # 30 dk

def get(url):
    req = urllib.request.Request(url, headers={"User-Agent":"Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=25) as r:
        return r.read().decode(errors="ignore")

def get_json(url):
    return json.loads(get(url))

def post(url, data):
    data = urllib.parse.urlencode(data).encode()
    req = urllib.request.Request(url, data=data)
    urllib.request.urlopen(req, timeout=20)

def send(msg):
    post(
        f"https://api.telegram.org/bot{TOKEN}/sendMessage",
        {"chat_id": CHAT_ID, "text": msg[:4000]}
    )

def format_num(n):
    if n is None:
        return "N/A"
    n = float(n)
    if n >= 1_000_000_000:
        return f"{n/1_000_000_000:.2f}B"
    if n >= 1_000_000:
        return f"{n/1_000_000:.2f}M"
    if n >= 1_000:
        return f"{n/1_000:.2f}K"
    if n >= 1:
        return f"{n:.4f}"
    return f"{n:.8f}"

def get_binance_symbols():
    d = get_json("https://api.binance.com/api/v3/exchangeInfo")
    syms = set()
    for s in d.get("symbols", []):
        if (
            s.get("status") == "TRADING"
            and s.get("isSpotTradingAllowed") is True
            and s.get("quoteAsset") == "USDT"
        ):
            syms.add((s.get("baseAsset") or "").upper())
    return syms

def get_coingecko_candidates():
    coins = []
    # Küçük cap tarafını görmek için birkaç sayfa çekiyoruz
    for page in range(1, 5):
        url = (
            "https://api.coingecko.com/api/v3/coins/markets"
            f"?vs_currency=usd&order=market_cap_asc&per_page=100&page={page}"
            "&sparkline=false&price_change_percentage=24h"
        )
        try:
            data = get_json(url)
            coins.extend(data)
            time.sleep(1.2)
        except:
            pass
    return coins

def entry_analysis(c):
    low = c.get("low_24h") or 0
    high = c.get("high_24h") or 0
    price = c.get("current_price") or 0

    if not low or not high or high <= low or not price:
        return None, "Unknown", "No range data", None, None

    pos = (price - low) / (high - low)

    # entry zone
    if pos < 0.30:
        zone = "DIP"
        advice = "Agresif entry zone"
    elif pos < 0.60:
        zone = "GOOD"
        advice = "Mantıklı entry zone"
    elif pos < 0.80:
        zone = "RISKY"
        advice = "Pullback beklemek daha iyi"
    else:
        zone = "TOP"
        advice = "Geç kalınmış olabilir"

    # basit TP / SL
    tp1 = price * 1.15
    tp2 = price * 1.30
    sl = price * 0.92

    return pos, zone, advice, tp1, sl

def score_coin(c):
    mcap = c.get("market_cap") or 0
    vol = c.get("total_volume") or 0
    price = c.get("current_price") or 0
    change = c.get("price_change_percentage_24h") or 0
    ratio = (vol / mcap) if mcap else 0

    pos, zone, advice, tp1, sl = entry_analysis(c)

    score = 0

    # MCAP scoring
    if 5_000_000 <= mcap <= 20_000_000:
        score += 5
    elif 20_000_000 < mcap <= 50_000_000:
        score += 4
    elif 50_000_000 < mcap <= 120_000_000:
        score += 2

    # Liquidity / interest
    if ratio >= 0.20:
        score += 5
    elif ratio >= 0.10:
        score += 4
    elif ratio >= 0.05:
        score += 2

    if vol >= 10_000_000:
        score += 4
    elif vol >= 3_000_000:
        score += 3
    elif vol >= 1_000_000:
        score += 1

    # Momentum
    if 3 <= change <= 18:
        score += 4
    elif 0 <= change < 3:
        score += 2
    elif 18 < change <= 30:
        score += 1
    elif change > 35:
        score -= 3
    elif change < -10:
        score -= 2

    # Entry position in daily range
    if zone == "DIP":
        score += 4
    elif zone == "GOOD":
        score += 3
    elif zone == "RISKY":
        score += 0
    elif zone == "TOP":
        score -= 4

    return {
        "score": score,
        "ratio": ratio,
        "change": change,
        "zone": zone,
        "advice": advice,
        "tp1": tp1,
        "sl": sl,
        "position": pos,
        "price": price,
    }

def classify_potential(score):
    if score >= 14:
        return "HIGH"
    if score >= 10:
        return "MEDIUM-HIGH"
    if score >= 7:
        return "MEDIUM"
    return "LOW"

def build_candidates():
    binance_syms = get_binance_symbols()
    cg = get_coingecko_candidates()

    out = []

    for c in cg:
        sym = (c.get("symbol") or "").upper()
        mcap = c.get("market_cap") or 0
        vol = c.get("total_volume") or 0

        if sym not in binance_syms:
            continue
        if mcap < MIN_MCAP or mcap > MAX_MCAP:
            continue
        if vol < MIN_VOL:
            continue

        metrics = score_coin(c)
        ratio = metrics["ratio"]
        potential = classify_potential(metrics["score"])

        if ratio < MIN_VOL_MCAP_RATIO:
            continue
        if potential == "LOW":
            continue
        if metrics["zone"] == "TOP":
            continue  # geç kalınmış coinleri kes

        out.append({
            "name": c.get("name"),
            "symbol": sym,
            "mcap": mcap,
            "vol": vol,
            "price": metrics["price"],
            "ratio": ratio,
            "change": metrics["change"],
            "score": metrics["score"],
            "potential": potential,
            "zone": metrics["zone"],
            "advice": metrics["advice"],
            "tp1": metrics["tp1"],
            "sl": metrics["sl"],
            "position": metrics["position"],
        })

    out.sort(
        key=lambda x: (x["score"], x["ratio"], x["vol"]),
        reverse=True
    )
    return out[:MAX_RESULTS]

def make_report(cands):
    lines = ["🎯 BINANCE SNIPER FINAL", ""]
    if not cands:
        lines += ["Uygun aday bulunamadı."]
        return "\n".join(lines)

    for i, c in enumerate(cands, 1):
        pos_pct = int((c["position"] or 0) * 100) if c["position"] is not None else 0
        lines += [
            f"{i}) {c['name']} (${c['symbol']})",
            f"MCAP: {format_num(c['mcap'])} | VOL: {format_num(c['vol'])}",
            f"VOL/MCAP: {c['ratio']:.2f} | 24h: {c['change']:.2f}%",
            f"Price: {format_num(c['price'])}",
            f"📊 POTENTIAL: {c['potential']}",
            f"🎯 ENTRY: {c['zone']} ({pos_pct}% range)",
            f"⚠️ Not: {c['advice']}",
            f"TP1: {format_num(c['tp1'])} | SL: {format_num(c['sl'])}",
            ""
        ]
    return "\n".join(lines)

last_snapshot = ""

send("🎯 Sniper Final aktif")

while True:
    try:
        candidates = build_candidates()
        snapshot = "|".join(
            f"{c['symbol']}:{int(c['mcap'])}:{int(c['vol'])}:{c['zone']}"
            for c in candidates
        )

        if snapshot != last_snapshot:
            report = make_report(candidates)
            send(report)
            last_snapshot = snapshot

        time.sleep(SLEEP_SECONDS)

    except Exception as e:
        try:
            send("Sniper Final error: " + str(e))
        except:
            pass
        time.sleep(120)
'@

Set-Content -Path $path -Value $code -Encoding UTF8
python $path
