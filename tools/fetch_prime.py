# 東証プライム全銘柄の日足を取得し、年ごとの圧縮データ (site/y/YYYY.json) と manifest を作る
import io, json, os, sys, time, datetime as dt
import pandas as pd, requests, yfinance as yf

OUT = sys.argv[1] if len(sys.argv) > 1 else "site"
START = "2000-01-01"
MAIN = ["7203","6758","9984","6861","8306","9432","6501","8035","9983","7974","4063","6098","8058","4502","7267",
        "9433","6920","7011","9101","2914","4661","6594","8001","6367","4568","7741","3382","9201","8316","6702",
        "7201","4755","2802","6752","9020","8766","5401","6857","4385","3659","2413","6146","7832","9766"]
# 合併・再上場などで過去データが別会社のもの
FIRST = {"9201": "2012-09-19", "8766": "2005-10-03", "7832": "2005-09-29", "4568": "2005-09-28", "3382": "2005-09-01"}

def jpx_list():
    url = "https://www.jpx.co.jp/markets/statistics-equities/misc/tvdivq0000001vg2-att/data_j.xls"
    r = requests.get(url, timeout=60, headers={"User-Agent": "Mozilla/5.0"}); r.raise_for_status()
    df = pd.read_excel(io.BytesIO(r.content), dtype=str)
    df = df[df["市場・商品区分"].str.startswith("プライム")]
    return [(str(c).strip(), n.strip(), (s or "").strip()) for c, n, s in zip(df["コード"], df["銘柄名"], df["33業種区分"])]

def enc(vals):
    out, pv = [], 0
    for v in vals:
        p = int(round(v * 10)); d = p - pv; pv = p
        out.append("" if d == 0 else (("-" if d < 0 else "") + format(abs(d), "x")))
    return ",".join(out)

def main():
    os.makedirs(OUT + "/y", exist_ok=True)
    lst = jpx_list(); print("prime:", len(lst), flush=True)
    meta = {c: (n, s) for c, n, s in lst}
    codes = [c for c, _, _ in lst]
    closes, divs = {}, {}
    B = 100
    for k in range(0, len(codes), B):
        batch = codes[k:k + B]; tick = [c + ".T" for c in batch]
        for attempt in range(4):
            try:
                df = yf.download(tick, start=START, auto_adjust=False, actions=True, group_by="ticker", threads=True, progress=False)
                break
            except Exception as e:
                print("retry", k, e, flush=True); time.sleep(20 * (attempt + 1))
        for c in batch:
            try: sub = df[c + ".T"]
            except KeyError: continue
            cl = sub["Close"].dropna(); cl = cl[cl > 0]
            if c in FIRST: cl = cl[cl.index >= FIRST[c]]
            if len(cl) == 0: continue
            closes[c] = cl
            if "Dividends" in sub:
                dv = sub["Dividends"].dropna(); dv = dv[dv > 0]
                if c in FIRST: dv = dv[dv.index >= FIRST[c]]
                divs[c] = dv
        print("batch", k, len(closes), flush=True)
        time.sleep(2)
    n225 = yf.download("^N225", start=START, auto_adjust=False, progress=False)
    n225 = n225["Close"].squeeze().dropna()
    # 暦：トヨタの取引日
    cal = [d.strftime("%Y-%m-%d") for d in closes["7203"].index]
    cal_idx = pd.DatetimeIndex(pd.to_datetime(cal))
    frame = pd.DataFrame({c: s.reindex(s.index.union(cal_idx)).ffill().reindex(cal_idx) for c, s in closes.items()})
    # 上場前は NaN のまま（ffill しない）
    for c, s in closes.items():
        frame.loc[frame.index < s.index[0], c] = float("nan")
    # 1日だけの異常値
    arr = frame.values
    for j in range(arr.shape[1]):
        col = arr[:, j]
        for i in range(1, len(col) - 1):
            a, b, cc = col[i - 1], col[i], col[i + 1]
            if a == a and b == b and cc == cc and a > 0:
                r = b / a
                if (r > 1.4 or r < 0.7) and 0.85 < cc / a < 1.18: col[i] = a
    frame = pd.DataFrame(arr, index=frame.index, columns=frame.columns)
    nk = n225.reindex(n225.index.union(cal_idx)).ffill().reindex(cal_idx)
    d0 = dt.date.fromisoformat(cal[0]); dd = []; prev = d0
    for x in cal[1:]:
        t = dt.date.fromisoformat(x); dd.append(chr(48 + (t - prev).days)); prev = t
    years = {}
    for i, x in enumerate(cal):
        y = x[:4]; years.setdefault(y, [i, i]); years[y][1] = i
    ordered = sorted(frame.columns)
    first = {c: int(frame[c].first_valid_index() is not None and cal_idx.get_loc(frame[c].first_valid_index())) for c in ordered}
    man = {"v": 2, "last": cal[-1], "d0": cal[0], "dd": "".join(dd), "years": years,
           "n225": enc(nk.values.tolist()),
           "meta": [[c, meta[c][0], meta[c][1], first[c], 1 if c in MAIN else 0] for c in ordered]}
    tot = 0
    for y, (i0, i1) in years.items():
        t = []
        for c in ordered:
            v = frame[c].values[i0:i1 + 1]
            ok = [k for k in range(len(v)) if v[k] == v[k]]
            if not ok: continue
            s = ok[0]
            t.append([c, s, enc(v[s:].tolist())])
        dv = {}
        for c, s in divs.items():
            for d, a in s.items():
                x = d.strftime("%Y-%m-%d")
                if x[:4] == y and x in cal:
                    dv.setdefault(c, []).append([cal.index(x) - i0, round(float(a) * 100)])
        js = json.dumps({"y": y, "i0": i0, "i1": i1, "t": t, "dv": dv}, ensure_ascii=False, separators=(",", ":"))
        open(f"{OUT}/y/{y}.json", "w").write(js); tot += len(js)
        print(y, len(t), round(len(js) / 1e6, 2), "MB", flush=True)
    if len(closes) < 1000: sys.exit("too few tickers: %d" % len(closes))
    json.dump(man, open(f"{OUT}/manifest.json", "w"), ensure_ascii=False, separators=(",", ":"))
    print("tickers", len(closes), "total", round(tot / 1e6, 1), "MB", "manifest", round(os.path.getsize(f"{OUT}/manifest.json") / 1e3), "KB")

main()
