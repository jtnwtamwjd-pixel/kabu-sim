import yfinance as yf, json, os, time
codes = ["^N225","1306","7203","6758","9984","6861","8306","9432","6501","8035","9983","7974","4063","6098","8058","4502","7267","9433","6920","7011","9101","2914","4661","6594","8001","6367","4568","7741","3382","9201","8316","6702","7201","4755","2802","6752","9020","8766","5401","6857","4385","3659","2413","6146","7832","9766"]
os.makedirs("data", exist_ok=True)
out = {}
for c in codes:
    t = c if c.startswith("^") else c + ".T"
    for i in range(3):
        try:
            tk = yf.Ticker(t)
            h = tk.history(start="2000-01-01", auto_adjust=False, actions=True)
            if len(h) == 0: raise Exception("empty")
            name = ""
            try:
                info = tk.info; name = info.get("shortName") or info.get("longName") or ""
            except Exception: pass
            h = h[h["Close"] > 0]
            out[c] = {
                "name": name,
                "d": [x.strftime("%Y-%m-%d") for x in h.index],
                "o": [round(float(v), 2) for v in h["Open"]],
                "h": [round(float(v), 2) for v in h["High"]],
                "l": [round(float(v), 2) for v in h["Low"]],
                "c": [round(float(v), 2) for v in h["Close"]],
                "v": [int(v) for v in h["Volume"]],
                "div": {x.strftime("%Y-%m-%d"): round(float(v), 2) for x, v in h["Dividends"].items() if v > 0},
                "split": {x.strftime("%Y-%m-%d"): float(v) for x, v in h["Stock Splits"].items() if v > 0},
            }
            print(c, name, len(h), h.index[0], h.index[-1])
            break
        except Exception as e:
            print("ERR", c, e); time.sleep(3)
json.dump(out, open("data/raw.json", "w"), ensure_ascii=False, separators=(",", ":"))
print(os.path.getsize("data/raw.json"))
