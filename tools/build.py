# raw.json (yfinance) -> data.json (compact, used by index.html)
import json, sys, datetime as dt
from collections import Counter
raw = json.load(open(sys.argv[1] if len(sys.argv) > 1 else "data/raw.json"))
out_path = sys.argv[2] if len(sys.argv) > 2 else "data.json"
# listing / data-quality start dates (merger-formed companies, relisting, etc.)
START = {"9201": "2012-09-19", "8766": "2005-10-03", "7832": "2005-09-29",
         "4568": "2005-09-28", "3382": "2005-09-01"}
# unadjusted splits in the source: (code, first date of new price basis, ratio)
FIX = [("1306", "2015-01-05", 10.0)]
cnt = Counter()
for k, v in raw.items():
    if k != "^N225": cnt.update(v["d"])
ntick = len(raw) - 1
cal = sorted(x for x, n in cnt.items() if n >= max(5, ntick * 0.4))
idx = {x: i for i, x in enumerate(cal)}
d0 = dt.date.fromisoformat(cal[0])
dd, prev = [], d0
for x in cal[1:]:
    t = dt.date.fromisoformat(x); dd.append(chr(48 + (t - prev).days)); prev = t
res = {"v": 1, "last": cal[-1], "d0": cal[0], "dd": "".join(dd), "t": []}
for k, v in raw.items():
    code = "N225" if k == "^N225" else k
    st = START.get(code, "0000")
    rows = [(x, c) for x, c in zip(v["d"], v["c"]) if x in idx and x >= st and c > 0]
    divs = dict(v["div"])
    for fc, fd, r in FIX:
        if fc == code:
            rows = [(x, c / r if x < fd else c) for x, c in rows]
            divs = {x: (a / r if x < fd else a) for x, a in divs.items()}
    if not rows: continue
    by = dict(rows)
    s = idx[rows[0][0]]
    series, last = [], None
    for x in cal[s:]:
        c = by.get(x, last); series.append(c); last = c
    # one-day spikes that revert
    for i in range(1, len(series) - 1):
        a, b, c = series[i - 1], series[i], series[i + 1]
        if (b / a > 1.4 or b / a < 0.7) and 0.85 < c / a < 1.18: series[i] = a
    p10 = [round(c * 10) for c in series]
    deltas, pv = [], 0
    for p in p10:
        dlt = p - pv; pv = p
        deltas.append("" if dlt == 0 else (("-" if dlt < 0 else "") + format(abs(dlt), "x")))
    dv = [[idx[x] - s, round(a * 100)] for x, a in sorted(divs.items()) if x in idx and idx[x] >= s]
    res["t"].append({"c": code, "s": s, "p": ",".join(deltas), "dv": dv})
if len(res["t"]) < 40: sys.exit("too few tickers: %d" % len(res["t"]))
json.dump(res, open(out_path, "w"), separators=(",", ":"))
print(out_path, len(cal), cal[0], cal[-1], len(res["t"]), round(len(json.dumps(res, separators=(",", ":"))) / 1e6, 2), "MB")
if len(sys.argv) > 4:  # build.py raw.json data.json src.html index.html
    open(sys.argv[4], "w").write(open(sys.argv[3]).read().replace("__DATA__", open(out_path).read()))
