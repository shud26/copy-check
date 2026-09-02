"""키가 게이트웨이에 전파될 때까지 기다린다. 되면 즉시 알려준다."""
import time, sys
import graph
SG = "5zvR82QoaXYFyDEKLZ9t6v9adgnptxYpKpSbxtgVENFV"
tries = int(sys.argv[1]) if len(sys.argv) > 1 else 12
for i in range(1, tries + 1):
    try:
        n = graph.health(SG)
        print(f"\n✅ {i}번째 시도에서 통과 — 색인 블록 {n:,}")
        sys.exit(0)
    except RuntimeError as e:
        msg = str(e)[:50]
        print(f"  {i:>2}/{tries}  {msg}", flush=True)
        if i < tries:
            time.sleep(30)
print("\n⏳ 아직 반영 안 됨. 몇십 분 더 걸릴 수 있음.")
sys.exit(1)
