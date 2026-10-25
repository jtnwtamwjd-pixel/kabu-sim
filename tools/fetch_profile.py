# 企業プロフィール：Wikidata/Wikipedia（概要・設立・本社）＋ Yahoo Finance（時価総額・PER など）→ data/profile.json
import json, os, re, sys, time, unicodedata
import requests, yfinance as yf

OUT = sys.argv[1] if len(sys.argv) > 1 else "data/profile.json"
MAN = sys.argv[2] if len(sys.argv) > 2 else "site/manifest.json"
UA = {"User-Agent": "kabu-sim/1.0 (https://github.com/jtnwtamwjd-pixel/kabu-sim)"}
META = {m[0]: m for m in json.load(open(MAN))["meta"]}
codes = list(META)
BASE = os.environ.get("BASE")  # 既存の profile.json を使い、Wikipedia 部分だけやり直す
prof = {c: {} for c in codes}
if BASE:
    for c, p in json.load(open(BASE))["p"].items():
        if c in prof: prof[c] = p

Q = """SELECT ?item ?code ?article ?inception ?hqLabel ?emp WHERE {
 ?item p:P414 ?st . ?st ps:P414 wd:Q217475 ; pq:P249 ?code .
 OPTIONAL { ?article schema:about ?item ; schema:isPartOf <https://ja.wikipedia.org/> . }
 OPTIONAL { ?item wdt:P571 ?inception }
 OPTIONAL { ?item wdt:P159 ?hq }
 OPTIONAL { ?item wdt:P1128 ?emp }
 SERVICE wikibase:label { bd:serviceParam wikibase:language "ja,en". }
}"""
try:
    r = requests.get("https://query.wikidata.org/sparql", params={"query": Q, "format": "json"}, headers=UA, timeout=120)
    rows = r.json()["results"]["bindings"]; print("wikidata rows", len(rows), flush=True)
    for b in rows:
        c = unicodedata.normalize("NFKC", b["code"]["value"]).strip()
        if c not in prof: continue
        p = prof[c]
        if "article" in b and "wt" not in p: p["wt"] = requests.utils.unquote(b["article"]["value"].rsplit("/wiki/", 1)[1]).replace("_", " ")
        if "inception" in b and "est" not in p:
            m = re.match(r"(-?\d{4})-(\d\d)", b["inception"]["value"])
            if m: p["est"] = f"{int(m.group(1))}年{int(m.group(2))}月" if m.group(2) != "01" else f"{int(m.group(1))}年"
        if "hqLabel" in b and "hq" not in p and not re.match(r"^Q\d+$", b["hqLabel"]["value"]): p["hq"] = b["hqLabel"]["value"]
        if "emp" in b:
            try: p["wemp"] = max(p.get("wemp", 0), int(float(b["emp"]["value"])))
            except ValueError: pass
except Exception as e:
    print("wikidata fail", e, flush=True)

CORP = re.compile(r"(株式会社|会社|企業|メーカー|持株会社|銀行|グループ)")
def extracts(pairs, check):
    """pairs: [(code, title)] → 見つかった code の set"""
    found = set()
    for k in range(0, len(pairs), 20):
        chunk = pairs[k:k + 20]
        try:
            r = requests.get("https://ja.wikipedia.org/w/api.php", params={"action": "query", "prop": "extracts|pageprops", "exintro": 1, "explaintext": 1,
                  "exsentences": 3, "exlimit": 20, "redirects": 1, "format": "json", "titles": "|".join(t for _, t in chunk)}, headers=UA, timeout=60).json()
            q = r.get("query", {})
            norm = {x["from"]: x["to"] for x in q.get("normalized", []) + q.get("redirects", [])}
            pages = {pg["title"]: pg for pg in q.get("pages", {}).values()}
            for c, t in chunk:
                tt = norm.get(t, t); tt = norm.get(tt, tt); pg = pages.get(tt)
                if not pg or "missing" in pg or "disambiguation" in pg.get("pageprops", {}): continue
                x = re.sub(r"\s*（[^）]*(英|英語|英称|英文社名)[^）]*）", "", pg.get("extract", "")).strip()
                x = re.sub(r"\n+", " ", x)
                if not x or (check and not CORP.search(x[:120])): continue
                prof[c]["d"] = x[:260]; prof[c]["wt"] = tt; found.add(c)
        except Exception as e:
            print("wiki fail", k, e, flush=True)
        time.sleep(0.5)
    return found

extracts([(c, p["wt"]) for c, p in prof.items() if p.get("wt") and not p.get("d")], False)
def base_name(n):
    return re.sub(r"\s+", "", n)
for variant in (lambda n: n, lambda n: n + " (企業)", lambda n: "株式会社" + n, lambda n: n.replace("ホールディングス", "") if "ホールディングス" in n else None):
    miss = [(c, variant(base_name(META[c][1]))) for c in codes if not prof[c].get("d")]
    miss = [(c, t) for c, t in miss if t]
    got = extracts(miss, True)
    print("name lookup", len(miss), "found", len(got), flush=True)
print("descriptions", sum(1 for p in prof.values() if p.get("d")), flush=True)
if BASE:
    json.dump({"at": time.strftime("%Y-%m-%d"), "p": prof}, open(OUT, "w"), ensure_ascii=False, separators=(",", ":"))
    print("done (wiki only)", os.path.getsize(OUT)); sys.exit(0)

ok = 0
for i, c in enumerate(codes):
    for attempt in range(3):
        try:
            tk = yf.Ticker(c + ".T"); info = tk.info or {}
            p = prof[c]
            try:
                bs = tk.balance_sheet
                if bs is not None and not bs.empty:
                    col = bs.columns[0]
                    eq = next((bs.at[k, col] for k in ("Stockholders Equity", "Common Stock Equity", "Total Equity Gross Minority Interest") if k in bs.index and bs.at[k, col] == bs.at[k, col]), None)
                    ta = bs.at["Total Assets", col] if "Total Assets" in bs.index else None
                    if eq and ta and ta == ta and ta > 0: p["eqr"] = round(float(eq) / float(ta), 3)
            except Exception:
                pass
            for src, dst, f in [("marketCap", "mc", int), ("trailingPE", "per", float), ("priceToBook", "pbr", float), ("returnOnEquity", "roe", float),
                                ("totalRevenue", "rev", int), ("operatingMargins", "opm", float), ("fullTimeEmployees", "emp", int), ("website", "web", str)]:
                v = info.get(src)
                if v not in (None, "", "Infinity"):
                    try: p[dst] = round(f(v), 3) if f is float else f(v)
                    except (TypeError, ValueError): pass
            ok += 1; break
        except Exception as e:
            if "Too Many Requests" in str(e) or "Rate" in str(e): time.sleep(30)
            else: time.sleep(2)
    if i % 100 == 0: print("info", i, ok, flush=True)
    time.sleep(0.25)
for c, p in prof.items():
    if "emp" not in p and p.get("wemp"): p["emp"] = p["wemp"]
    p.pop("wemp", None)
os.makedirs(os.path.dirname(OUT) or ".", exist_ok=True)
json.dump({"at": time.strftime("%Y-%m-%d"), "p": prof}, open(OUT, "w"), ensure_ascii=False, separators=(",", ":"))
print("done", ok, sum(1 for p in prof.values() if p.get("d")), os.path.getsize(OUT))
