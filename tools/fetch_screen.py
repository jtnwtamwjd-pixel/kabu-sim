# 東証全銘柄（プライム/スタンダード/グロース）の PBR・ROE・自己資本比率などを取得 → data/screen.json
import io, json, os, re, sys, time, unicodedata
from concurrent.futures import ThreadPoolExecutor
import pandas as pd, requests, yfinance as yf

OUT = sys.argv[1] if len(sys.argv) > 1 else "data/screen.json"
LIMIT = int(os.environ.get("LIMIT", "0"))  # テスト用に銘柄数を絞る
COLS = ["code", "name", "mkt", "sec", "px", "mc", "pbr", "roe", "eqr", "per", "dy", "opm", "fy", "at"]

def jpx_list():
    H = {"User-Agent": "Mozilla/5.0"}
    page = requests.get("https://www.jpx.co.jp/markets/statistics-equities/misc/01.html", timeout=60, headers=H).text
    m = re.search(r'href="([^"]+data_j\.xlsx?)"', page)
    url = "https://www.jpx.co.jp" + m.group(1) if m.group(1).startswith("/") else m.group(1)
    r = requests.get(url, timeout=60, headers=H); r.raise_for_status()
    df = pd.read_excel(io.BytesIO(r.content), dtype=str)
    print(df["市場・商品区分"].value_counts().to_dict(), flush=True)
    df = df[df["市場・商品区分"].str.match(r"^(プライム|スタンダード|グロース)")]
    return [(str(c).strip(), unicodedata.normalize("NFKC", n).strip(), re.match(r"^(プライム|スタンダード|グロース)", k).group(1), (s or "").strip())
            for c, n, k, s in zip(df["コード"], df["銘柄名"], df["市場・商品区分"], df["33業種区分"])]

def row_of(bs, keys):
    if bs is None or bs.empty: return None
    col = bs.columns[0]
    for k in keys:
        if k in bs.index:
            v = bs.at[k, col]
            if v == v and v is not None: return float(v)
    return None

def fetch(code):
    for attempt in range(4):
        try:
            tk = yf.Ticker(code + ".T"); info = tk.info or {}
            if not info or info.get("quoteType") not in (None, "EQUITY"): return None
            px = info.get("currentPrice") or info.get("regularMarketPrice") or info.get("previousClose")
            r = {"px": px, "mc": info.get("marketCap"), "per": info.get("trailingPE"), "opm": info.get("operatingMargins"), "roe": info.get("returnOnEquity")}
            bps = info.get("bookValue")
            r["pbr"] = px / bps if px and bps and bps > 0 else info.get("priceToBook")
            if px and info.get("dividendRate"): r["dy"] = info["dividendRate"] / px
            elif info.get("trailingAnnualDividendYield") is not None: r["dy"] = info["trailingAnnualDividendYield"]
            bs = tk.balance_sheet
            eq = row_of(bs, ["Stockholders Equity", "Common Stock Equity"])
            ta = row_of(bs, ["Total Assets"])
            if eq is not None and ta: r["eqr"] = eq / ta
            if bs is not None and not bs.empty: r["fy"] = bs.columns[0].strftime("%Y-%m")
            if r["roe"] is None and eq and eq > 0:
                ni = row_of(tk.income_stmt, ["Net Income Common Stockholders", "Net Income"])
                if ni is not None: r["roe"] = ni / eq
            if r["pbr"] is None and px and eq and eq > 0 and info.get("sharesOutstanding"):
                r["pbr"] = px / (eq / info["sharesOutstanding"])
            return r
        except Exception as e:
            msg = str(e)
            time.sleep(30 * (attempt + 1) if ("Too Many" in msg or "Rate" in msg or "401" in msg) else 2)
    return None

def rnd(v, k):
    if v is None or v != v or v in (float("inf"), float("-inf")): return None
    if k in ("mc",): return int(v)
    if k in ("px",): return round(float(v), 1)
    if k in ("pbr", "per"): return round(float(v), 2)
    return round(float(v), 4)

def main():
    lst = jpx_list()
    if LIMIT: lst = lst[:LIMIT]
    print("tickers", len(lst), flush=True)
    prev = {}
    if os.path.exists(OUT):
        d = json.load(open(OUT)); prev = {r[0]: dict(zip(d["cols"], r)) for r in d["rows"]}
    today = time.strftime("%Y-%m-%d")
    res, ok = {}, 0
    def job(item):
        return item, fetch(item[0])
    with ThreadPoolExecutor(6) as ex:
        for i, (item, r) in enumerate(ex.map(job, lst)):
            res[item[0]] = (item, r)
            if r: ok += 1
            if i % 200 == 0: print("fetched", i, ok, flush=True)
    rows = []
    for code, (item, r) in res.items():
        _, name, mkt, sec = item
        if r:
            rec = {"code": code, "name": name, "mkt": mkt, "sec": sec, "at": today, **{k: rnd(r.get(k), k) for k in COLS[4:] if k not in ("fy", "at")}, "fy": r.get("fy")}
        elif code in prev:  # 取得失敗時は前回値を残す
            rec = {**prev[code], "name": name, "mkt": mkt, "sec": sec}
        else:
            continue
        rows.append([rec.get(k) for k in COLS])
    print("ok", ok, "rows", len(rows), flush=True)
    if not LIMIT and ok < len(lst) * 0.6: sys.exit("too many failures: %d/%d" % (ok, len(lst)))
    os.makedirs(os.path.dirname(OUT) or ".", exist_ok=True)
    json.dump({"at": today, "cols": COLS, "rows": rows}, open(OUT, "w"), ensure_ascii=False, separators=(",", ":"))
    print("done", os.path.getsize(OUT))

main()
