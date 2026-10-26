# 東証全銘柄（プライム/スタンダード/グロース）の PBR・ROE・自己資本比率などを取得 → data/screen.json
import io, json, os, re, sys, time, unicodedata
from concurrent.futures import ThreadPoolExecutor
import pandas as pd, requests, yfinance as yf

OUT = sys.argv[1] if len(sys.argv) > 1 else "data/screen.json"
LIMIT = int(os.environ.get("LIMIT", "0"))  # テスト用に銘柄数を絞る
COLS = ["code", "name", "mkt", "sec", "px", "mc", "pbr", "roe", "eqr", "per", "dy", "opm", "fy", "at",
        "fpe", "psr", "ev", "ncr", "kncr", "roa", "npm", "gpm", "cr", "de", "rg1", "rg3", "og1", "ng1", "po", "dgy", "dny", "h52", "r1y", "beta"]
INFO = {"fpe": "forwardPE", "psr": "priceToSalesTrailing12Months", "ev": "enterpriseToEbitda", "roa": "returnOnAssets",
        "npm": "profitMargins", "gpm": "grossMargins", "cr": "currentRatio", "po": "payoutRatio", "r1y": "52WeekChange", "beta": "beta"}

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

def growth(st, key, years):
    if st is None or st.empty or key not in st.index: return None
    v = [x for x in st.loc[key].tolist() if x == x]
    if len(v) <= years or v[years] <= 0 or v[0] <= 0: return None
    return (v[0] / v[years]) ** (1 / years) - 1

def div_streaks(dv):
    """暦年ごとの1株配当から（連続増配年数, 減配なし年数）。今年は途中なので除く"""
    if dv is None or len(dv) == 0: return 0, 0
    yr = dv.groupby(dv.index.year).sum()
    yr = yr[yr.index < time.localtime().tm_year]
    v = yr.tolist()
    if not v or v[-1] <= 0: return 0, 0
    up = nd = 0
    for i in range(len(v) - 1, 0, -1):
        if v[i] > v[i - 1] * 1.001 and up == len(v) - 1 - i: up += 1
        if v[i] >= v[i - 1] * 0.999 and v[i - 1] > 0: nd += 1
        else: break
    return up, nd

def fetch(code):
    for attempt in range(4):
        try:
            tk = yf.Ticker(code + ".T"); info = tk.info or {}
            if not info or info.get("quoteType") not in (None, "EQUITY"): return None
            px = info.get("currentPrice") or info.get("regularMarketPrice") or info.get("previousClose")
            mc = info.get("marketCap")
            r = {"px": px, "mc": mc, "per": info.get("trailingPE"), "opm": info.get("operatingMargins"), "roe": info.get("returnOnEquity")}
            for k, src in INFO.items(): r[k] = info.get(src)
            for k in ("npm", "gpm"):  # Yahoo は欠損を 0 で返すことがある
                if r[k] == 0: r[k] = None
            if info.get("debtToEquity") is not None: r["de"] = info["debtToEquity"] / 100
            if px and info.get("fiftyTwoWeekHigh"): r["h52"] = px / info["fiftyTwoWeekHigh"] - 1
            bps = info.get("bookValue")
            r["pbr"] = px / bps if px and bps and bps > 0 else info.get("priceToBook")
            if px and info.get("dividendRate"): r["dy"] = info["dividendRate"] / px
            elif info.get("trailingAnnualDividendYield") is not None: r["dy"] = info["trailingAnnualDividendYield"]
            bs = tk.balance_sheet
            eq = row_of(bs, ["Stockholders Equity", "Common Stock Equity"])
            ta = row_of(bs, ["Total Assets"])
            if eq is not None and ta: r["eqr"] = eq / ta
            if bs is not None and not bs.empty: r["fy"] = bs.columns[0].strftime("%Y-%m")
            if mc:
                cash = row_of(bs, ["Cash Cash Equivalents And Short Term Investments", "Cash And Cash Equivalents"])
                debt = row_of(bs, ["Total Debt"]) or 0
                if cash is not None: r["ncr"] = (cash - debt) / mc
                ca = row_of(bs, ["Current Assets"]); tl = row_of(bs, ["Total Liabilities Net Minority Interest"])
                inv = row_of(bs, ["Investmentin Financial Assets", "Available For Sale Securities", "Long Term Equity Investment", "Investments And Advances"]) or 0
                if ca is not None and tl is not None: r["kncr"] = (ca + inv * 0.7 - tl) / mc
            inc = tk.income_stmt
            r["rg1"] = growth(inc, "Total Revenue", 1); r["rg3"] = growth(inc, "Total Revenue", 3)
            r["og1"] = growth(inc, "Operating Income", 1); r["ng1"] = growth(inc, "Net Income Common Stockholders", 1)
            if r["roe"] is None and eq and eq > 0:
                ni = row_of(inc, ["Net Income Common Stockholders", "Net Income"])
                if ni is not None: r["roe"] = ni / eq
            if r["pbr"] is None and px and eq and eq > 0 and info.get("sharesOutstanding"):
                r["pbr"] = px / (eq / info["sharesOutstanding"])
            try: r["dgy"], r["dny"] = div_streaks(tk.dividends)
            except Exception: pass
            return r
        except Exception as e:
            msg = str(e)
            time.sleep(30 * (attempt + 1) if ("Too Many" in msg or "Rate" in msg or "401" in msg) else 2)
    return None

DEC = {"px": 1, "pbr": 2, "per": 2, "fpe": 2, "psr": 2, "ev": 2, "cr": 2, "de": 2, "beta": 2}
def rnd(v, k):
    if v is None or isinstance(v, str): return None
    try: v = float(v)
    except (TypeError, ValueError): return None
    if v != v or v in (float("inf"), float("-inf")): return None
    if k == "mc": return int(v)
    if k in ("dgy", "dny"): return int(v)
    return round(v, DEC.get(k, 4))

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
    with ThreadPoolExecutor(8) as ex:
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
