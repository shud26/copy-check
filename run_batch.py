"""여러 지갑을 한 번에 채점한다.

⚠️ 지갑 하나가 실패해도 나머지는 계속 간다. 그리고 실패한 지갑을
   조용히 빼지 않고 목록에 남긴다 — "성적이 없는 지갑"과
   "우리가 못 본 지갑"은 다르기 때문이다.
"""
import datetime as dt, sys, time
import graph, fetch
from verdict import score, report

SG = "5zvR82QoaXYFyDEKLZ9t6v9adgnptxYpKpSbxtgVENFV"
WALLETS = [
 "0x64c7663bffe42724b6c30d7b88e69435f15fbbc8",
 "0x9235910f410478b89f86e06be0e4535335af6dea",
 "0xfc9928f6590d853752824b0b403a6ae36785e535",
 "0xf70da97812cb96acdf810712aa562db8dfa3dbef",
 "0x0b7b5120a8d7fea5e899ea0e2ecf4f0466c08bad",
]
head = graph.health(SG)
FROM = head - 250_000
SINCE = int((dt.datetime.now(dt.UTC) - dt.timedelta(days=45)).timestamp())
print(f"블록 {FROM:,} ~ {head:,}  (약 5주)\n")

vs, failed = [], []
for i, w in enumerate(WALLETS, 1):
    t = time.time()
    try:
        sw, meta = fetch.fetch(SG, w, FROM, SINCE, max_pages=4)
        v = score(w[:10], "ethereum", sw, pinned_block=FROM)
        vs.append(v)
        g = meta.get("gas", {})
        tag = " ⚠️일부만" if meta["truncated"] else ""
        print(f"  [{i}/{len(WALLETS)}] {w[:12]}…  원본 {meta['raw']:>5} → 사용 {meta['used']:>4}"
              f" · 완결 {v.closed:>4} · 가스 {v.gas:>8.4f} ETH"
              f" · {time.time()-t:>5.0f}초{tag}", flush=True)
    except Exception as e:
        failed.append((w, str(e)[:60]))
        print(f"  [{i}/{len(WALLETS)}] {w[:12]}…  🔴 {str(e)[:50]}", flush=True)

print()
print(report(vs, gate=20))
print()
for v in vs:
    j, why = v.judge()
    print(f"  {v.wallet}  {j}\n      {why}")
if failed:
    print(f"\n⚠️ 실패 {len(failed)}건 (성적 없음이 아니라 못 본 것):")
    for w, e in failed:
        print(f"   {w[:12]}…  {e}")
