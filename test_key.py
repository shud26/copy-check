"""API 키가 살아있는지, 실제 데이터가 오는지 확인."""
import json, os, pathlib, urllib.request

for ln in pathlib.Path(".env").read_text().splitlines():
    ln = ln.strip()
    if ln and not ln.startswith("#") and "=" in ln:
        k, v = ln.split("=", 1); os.environ.setdefault(k.strip(), v.strip())

KEY = os.environ["GRAPH_API_KEY"]
# 유니스왑 v3 이더리움 — 가장 널리 쓰이는 공개 서브그래프
SUBGRAPH = "5zvR82QoaXYFyDEKLZ9t6v9adgnptxYpKpSbxtgVENFV"
URL = f"https://gateway.thegraph.com/api/{KEY}/subgraphs/id/{SUBGRAPH}"

Q = """{ swaps(first: 3, orderBy: timestamp, orderDirection: desc) {
  timestamp origin amountUSD
  token0 { symbol } token1 { symbol } } }"""

req = urllib.request.Request(URL, data=json.dumps({"query": Q}).encode(),
                             headers={"Content-Type": "application/json"})
try:
    r = json.load(urllib.request.urlopen(req, timeout=30))
except Exception as e:
    print(f"🔴 실패: {e}"); raise SystemExit(1)

if "errors" in r:
    print("🔴 응답 에러:", json.dumps(r["errors"], ensure_ascii=False)[:300]); raise SystemExit(1)

import datetime as dt
sw = r["data"]["swaps"]
print(f"✅ 키 정상 · 최근 스왑 {len(sw)}건 수신\n")
for s in sw:
    t = dt.datetime.fromtimestamp(int(s["timestamp"]), dt.UTC).strftime("%m-%d %H:%M")
    print(f"  {t}  {s['token0']['symbol']:>6} / {s['token1']['symbol']:<6} "
          f"${float(s['amountUSD']):>12,.0f}   {s['origin'][:10]}…")
