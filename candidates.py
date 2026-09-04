#!/usr/bin/env python3
"""관찰 후보 지갑을 찾는다 — **채점이 가능한 지갑**을 찾는 것이지,
좋은 지갑을 찾는 것이 아니다.

⚠️⚠️ 이 파일은 후보의 과거 손익을 **절대 계산하지 않는다.**

    손익을 보고 고르면 그 순간 "답을 보고 고른 것"이 되고,
    이 도구 전체의 전제(미래로만 센다)가 무너진다. 등록 시점을 못박는
    scan.py 의 노력이 후보 선별 단계에서 통째로 무의미해진다.

    그래서 이 파일은 **가격을 아예 읽지 않는다.** 왕복 횟수를 셀 때도
    수량만 쓴다(count_roundtrips). 손익을 계산하고 싶어도 재료가 없다.
    이건 실수를 막는 장치이지 스타일이 아니다 — 고치지 말 것.

무엇을 거르는가
    NOTES 7번: "자주 등장하는 지갑"으로 뽑으면 전부 봇이다.
    최근 스왑에서 빈도순 상위 6개를 뽑았더니 6개 전부 봇이거나 완결 0건이었다.
    자주 등장한다는 게 곧 봇의 정의다. 그래서 빈도는 **상한과 하한을 동시에** 건다.

    quiet-64c7: 스왑 4,000건을 받아왔는데 **완결이 0건**이었다.
    사기만 하고 팔지 않으면 영원히 ⏳ 표본 부족이다.
    → 매수와 매도가 **둘 다** 있어야 후보로 친다.

두 번에 나눠 본다
    1단계  최근 스왑 흐름을 훑어서 지갑 주소를 모은다 (가볍게, timestamp/origin 만)
    2단계  모인 주소를 하나씩 제대로 조회해서 빈도·완결·활동을 잰다

    왜 나누냐면, 1단계 표본만으로 빈도를 재면 **우리가 얼마나 봤나**가
    판단을 좌우한다(NOTES 9번과 같은 함정). 2단계에서 그 지갑의 실제
    관측 구간을 따로 재서 하루 빈도를 계산한다.

사용:
    python3 candidates.py                      기본값으로 후보 뽑기
    python3 candidates.py --rows 20000 --top 20
    python3 candidates.py --days 30 --min-per-day 0.5
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import pathlib
import sys
import time
from collections import Counter, deque
from concurrent.futures import ThreadPoolExecutor

import fetch
import graph

SG = "5zvR82QoaXYFyDEKLZ9t6v9adgnptxYpKpSbxtgVENFV"   # Uniswap v3 · Ethereum
OUT = pathlib.Path("out/candidates.json")
REG = pathlib.Path("wallets.json")

# ⚠️ 1단계는 timestamp/origin 만 받는다. 토큰이나 금액을 받으면 응답이 몇 배로
#    커지는데, 여기서 필요한 건 "누가 최근에 거래했나" 뿐이다.
#
# ⚠️ skip 으로 넘기지 않는다. The Graph 는 skip 상한이 5,000이라
#    그 너머는 조용히 실패한다. 대신 timestamp 를 커서로 써서 뒤로 넘긴다.
STREAM_Q = """
query($lt: BigInt!) {
  swaps(
    first: 1000,
    where: { timestamp_lt: $lt }
    orderBy: timestamp, orderDirection: desc
  ) { timestamp origin }
}"""


# ────────────────────────────────────────────── 1단계

def stream(rows_wanted: int, verbose: bool = True) -> tuple[Counter, dict]:
    """최근 스왑을 뒤로 훑으면서 지갑 주소를 센다.

    ⚠️ 받아온 구간의 실제 길이를 같이 돌려준다. 몇 시간치를 봤는지
       모르면 "이 지갑이 자주 거래한다"는 말에 아무 의미가 없다.
    """
    cursor = int(time.time()) + 1
    seen: Counter = Counter()
    rows = 0
    newest = oldest = None

    while rows < rows_wanted:
        d = graph.query(SG, STREAM_Q, {"lt": str(cursor)})
        got = d["swaps"]
        if not got:
            break
        for r in got:
            seen[r["origin"].lower()] += 1
        rows += len(got)
        ts = [int(r["timestamp"]) for r in got]
        newest = max(ts) if newest is None else max(newest, max(ts))
        oldest = min(ts) if oldest is None else min(oldest, min(ts))

        if verbose:
            span_h = (newest - oldest) / 3600
            print(f"  스왑 {rows:,}건 · 구간 {span_h:.1f}시간 · 지갑 {len(seen):,}개",
                  flush=True)

        if len(got) < 1000:
            break
        nxt = min(ts)
        if nxt >= cursor:
            # 같은 시각에 1,000건이 몰려 있어 커서가 안 밀린다. 여기서 멈춘다.
            break
        cursor = nxt

    span = max((newest or 0) - (oldest or 0), 1)
    return seen, {"rows": rows, "span_sec": span, "newest": newest, "oldest": oldest}


# ────────────────────────────────────────────── 왕복 세기 (가격 없이)

def count_roundtrips(swaps) -> tuple[int, int, int]:
    """FIFO로 왕복을 세되 **수량만 본다.**

    ⚠️ 일부러 가격을 안 받는다. 여기서 손익을 계산할 수 있게 만들면
       누군가(=나중의 나) 후보를 손익으로 고르게 된다.
       손익 판정은 등록하고 시간이 지난 뒤 verdict.py 가 할 일이다.

    반환: (완결 수, 매수 수, 매도 수)
    """
    lots: dict[str, deque] = {}
    closed = buys = sells = 0

    for s in sorted(swaps, key=lambda x: (x.block, x.ts)):
        if s.side == "buy":
            lots.setdefault(s.token, deque()).append(s.qty)
            buys += 1
            continue

        sells += 1
        remain, q = s.qty, lots.get(s.token)
        if not q:
            continue
        while remain > 1e-18 and q:
            take = min(remain, q[0])
            closed += 1
            q[0] -= take
            remain -= take
            if q[0] <= 1e-18:
                q.popleft()
    return closed, buys, sells


# ────────────────────────────────────────────── 2단계

def profile(addr: str, days: int, max_pages: int) -> dict:
    """지갑 하나를 제대로 재본다. 가스는 받지 않는다(후보 단계라 불필요).

    ⚠️ truncated 가 뜨면 이 지갑은 max_pages×1000건을 넘겼다는 뜻이다.
       그건 사람 빈도가 아니므로 봇으로 보고 뺀다. "덜 본 것"이 아니라
       "너무 많아서 못 다 본 것"이고, 그 자체가 결론이다.
    """
    since = int(time.time()) - days * 86400
    try:
        sw, meta = fetch.fetch(SG, addr, from_block=0, since_ts=since,
                               max_pages=max_pages, with_gas=False)
    except Exception as e:
        return {"addr": addr, "error": str(e)[:120]}

    if not sw:
        return {"addr": addr, "weth_swaps": 0, "note": "WETH 페어 거래 없음",
                "raw_swaps": meta["raw"]}

    ts = [s.ts for s in sw]
    span_days = max((max(ts) - min(ts)) / 86400, 0.5)
    closed, buys, sells = count_roundtrips(sw)

    return {
        "addr": addr,
        "weth_swaps": len(sw),
        "raw_swaps": meta["raw"],
        "skipped": meta["skipped"],
        "truncated": meta["truncated"],
        "buys": buys, "sells": sells,
        "tokens": len({s.token for s in sw}),
        "basket": sorted({s.token for s in sw}),
        "closed": closed,
        "span_days": round(span_days, 1),
        "per_day": round(len(sw) / span_days, 1),
        "closed_per_day": round(closed / span_days, 2),
        "last_seen": dt.datetime.fromtimestamp(max(ts), dt.UTC)
                       .strftime("%Y-%m-%d %H:%M UTC"),
        "idle_days": round((time.time() - max(ts)) / 86400, 1),
    }


# ────────────────────────────────────────────── 거르기

def keep(p: dict, a) -> tuple[bool, str]:
    """후보로 남길지. 탈락하면 이유를 같이 돌려준다.

    ⚠️ 탈락 사유를 버리지 않는다. 조건이 너무 빡빡해서 다 떨어진 건지,
       원래 그런 지갑이 없는 건지 구분되어야 한다.
    """
    if p.get("error"):
        return False, "조회 실패"
    if not p.get("weth_swaps"):
        return False, "WETH 페어 거래 없음"
    if p["truncated"]:
        return False, f"너무 많음(≥{a.max_pages * 1000:,}건) — 봇"
    if p["per_day"] >= a.bot_per_day:
        return False, f"하루 {p['per_day']}건 — 봇 기준({a.bot_per_day}) 이상"
    if p["per_day"] < a.min_per_day:
        return False, f"하루 {p['per_day']}건 — 너무 조용함"
    if p["sells"] == 0:
        return False, "판 적이 없음 — 완결이 안 생김"
    if p["closed"] == 0:
        return False, "완결 0건 — quiet-64c7 유형"
    if p["idle_days"] > a.max_idle:
        return False, f"{p['idle_days']}일째 조용 — 은퇴 의심"
    return True, ""


# ────────────────────────────────────────────── 실행

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rows", type=int, default=8000, help="1단계에서 훑을 스왑 수")
    ap.add_argument("--probe", type=int, default=60, help="2단계에서 조회할 지갑 수")
    ap.add_argument("--top", type=int, default=12, help="최종 후보 수")
    ap.add_argument("--days", type=int, default=21, help="2단계 관측 구간(일)")
    ap.add_argument("--max-pages", type=int, default=2, help="지갑당 최대 페이지")
    ap.add_argument("--bot-per-day", type=float, default=20.0, help="봇 상한(건/일)")
    ap.add_argument("--min-per-day", type=float, default=0.7, help="하한(건/일)")
    ap.add_argument("--max-idle", type=float, default=3.0, help="마지막 활동 허용(일)")
    ap.add_argument("--sort", choices=["human", "fast"], default="human",
                    help="human=조용한 순(기본) · fast=판정 빨리 나오는 순")
    ap.add_argument("--workers", type=int, default=6)
    a = ap.parse_args()

    print("⚠️ 이 목록은 '잘 버는 지갑'이 아니라 '채점이 가능한 지갑'입니다.")
    print("   과거 손익은 보지 않았습니다 — 보고 고르면 미래검증이 무의미해집니다.\n")

    print(f"1단계 — 최근 스왑 {a.rows:,}건 훑기")
    seen, meta = stream(a.rows)
    if not seen:
        print("  스왑을 못 받았습니다. .env 의 GRAPH_API_KEY 를 확인하세요.")
        sys.exit(1)

    span_h = meta["span_sec"] / 3600
    print(f"  → 스왑 {meta['rows']:,}건 · {span_h:.1f}시간 · 지갑 {len(seen):,}개\n")

    # ⚠️ 1단계 표본에서 이미 너무 자주 나온 주소는 2단계에 넣지 않는다.
    #    확인하려고 조회하는 데 드는 시간이 아깝고, 결과는 뻔하다.
    #    다만 몇 개를 그렇게 뺐는지는 남긴다.
    cap = max(int(a.bot_per_day * (span_h / 24) * 1.5), 3)
    loud = [w for w, n in seen.items() if n > cap]
    pool = [w for w, n in seen.items() if n <= cap]

    already = set()
    if REG.exists():
        already = {w["addr"].lower() for w in json.loads(REG.read_text())["wallets"]}
    pool = [w for w in pool if w not in already]

    # ⚠️ **적게 나온 쪽부터** 본다. 많이 나온 쪽이 아니다.
    #
    #    처음엔 "표본에 여러 번 나온 쪽이 살아있을 확률이 높다"고 생각해서
    #    빈도 내림차순으로 넘겼다. 결과는 후보 0개, 탈락 20개 중 12개가 봇이었다.
    #    NOTES 7번을 조건만 바꿔서 그대로 반복한 것이다.
    #
    #    1단계 구간은 30분 남짓이라 하루 43건짜리 봇도 딱 한 번 나온다.
    #    즉 **짧은 표본의 빈도로는 봇과 사람이 구분되지 않는다.**
    #    구분은 2단계(지갑별 실제 구간)에서만 가능하다.
    #    1단계가 할 수 있는 최선은 봇일 확률이 낮은 쪽부터 넘기는 것뿐이다.
    pool.sort(key=lambda w: seen[w])
    probe = pool[:a.probe]

    print(f"2단계 — 지갑 {len(probe)}개 조회 (최근 {a.days}일)")
    print(f"  1단계에서 뺀 것: 시끄러움 {len(loud):,}개(표본 {cap}건 초과) · "
          f"이미 등록됨 {len(already & set(seen)):,}개")

    t0 = time.time()
    with ThreadPoolExecutor(max_workers=a.workers) as ex:
        profs = list(ex.map(lambda w: profile(w, a.days, a.max_pages), probe))
    print(f"  → {time.time() - t0:.0f}초\n")

    # ⚠️ 주소별 빈도만으로는 봇 무리를 못 잡는다 (2026-09-04 실측).
    #
    #    처음 뽑은 후보 12개 중 7개가 **완전히 같은 바스켓**이었다:
    #        AAVE · LDO · LINK · UNI · USDC · USDT · WBTC
    #    각각 하루 9.6~10.8건. 한 사람이 주소를 쪼개서 굴리는 것이다.
    #
    #    verdict.py 의 봇 기준은 **주소 하나**의 하루 빈도다. 그래서
    #    하루 40건짜리 하나를 10건짜리 넷으로 나누면 넷 다 통과한다.
    #    빈도는 주소를 쪼개면 줄어들지만, **무엇을 사는지는 안 변한다.**
    #    그래서 바스켓을 지문으로 쓴다.
    #
    #    토큰 3종 미만은 지문으로 안 본다. USDC 하나만 굴리는 사람은
    #    실제로 흔해서, 겹친다고 한 무리라 할 근거가 없다.
    FLEET_MIN_TOKENS, FLEET_MIN_ADDRS = 3, 3
    sigs = Counter(tuple(p["basket"]) for p in profs
                   if p.get("basket") and len(p["basket"]) >= FLEET_MIN_TOKENS)
    fleets = {s: n for s, n in sigs.items() if n >= FLEET_MIN_ADDRS}

    kept, dropped = [], Counter()
    for p in profs:
        sig = tuple(p.get("basket") or ())
        if sig in fleets:
            dropped.update([f"같은 바스켓 {fleets[sig]}개 — 봇 무리 의심 "
                            f"({'·'.join(sig[:4])}…)"])
            continue
        ok, why = keep(p, a)
        (kept.append(p) if ok else dropped.update([why]))

    for p in kept:
        p["days_to_gate"] = (round(20 / p["closed_per_day"], 1)
                             if p["closed_per_day"] else None)

    # ⚠️ 기본 정렬을 "판정이 빨리 나오는 순"으로 두면 안 된다 (2026-09-04).
    #
    #    처음에 days_to_gate 오름차순으로 세웠더니 하루 8~16건짜리가
    #    위로 올라왔다. 20건을 빨리 채우니까 당연한 결과다.
    #    그런데 그건 **봇에 가까운 순서**다. 봇 상한(20건) 바로 아래가
    #    맨 위에 오게 된다.
    #
    #    빨리 보고 싶은 건 우리 사정이지 지갑의 성질이 아니다.
    #    정렬 기준이 찾으려는 것과 반대로 가면 필터를 아무리 조여도 소용없다.
    #    → 기본은 조용한 순(사람에 가까운 순). 대신 기다림이 길어진다.
    #      그 대가는 days_to_gate 로 그대로 보여준다.
    if a.sort == "fast":
        kept.sort(key=lambda p: p["days_to_gate"] or 9e9)
    else:
        kept.sort(key=lambda p: (p["per_day"], p["tokens"]))
    kept = kept[:a.top]

    print(f"탈락 {sum(dropped.values())}개")
    for why, n in dropped.most_common():
        print(f"    {n:>3}  {why}")

    if not kept:
        print("\n조건에 맞는 지갑이 없습니다. --rows 를 늘리거나 조건을 푸세요.")
    else:
        how = ("조용한 순 — 사람에 가까운 쪽부터" if a.sort == "human"
               else "판정이 빨리 나오는 순 — ⚠️ 봇에 가까운 쪽이 위로 옵니다")
        print(f"\n후보 {len(kept)}개 — {how}\n")
        print(f"  {'주소':<44}{'하루스왑':>9}{'하루완결':>9}{'토큰':>6}"
              f"{'20건까지':>10}{'마지막활동':>10}")
        print("  " + "-" * 88)
        for p in kept:
            print(f"  {p['addr']:<44}{p['per_day']:>9.1f}{p['closed_per_day']:>9.2f}"
                  f"{p['tokens']:>6}{(str(p['days_to_gate']) + '일'):>10}"
                  f"{(str(p['idle_days']) + '일 전'):>10}")

    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps({
        "generated_at": dt.datetime.now(dt.UTC).strftime("%Y-%m-%d %H:%M UTC"),
        "note": "채점 가능한 지갑 목록. 과거 손익으로 고르지 않았음.",
        "stream": {**meta, "span_hours": round(span_h, 1),
                   "wallets_seen": len(seen), "probed": len(probe)},
        "filters": vars(a),
        "dropped": dict(dropped),
        "candidates": kept,
    }, ensure_ascii=False, indent=2))
    print(f"\n→ {OUT}")

    if kept:
        print("\n마음에 드는 걸 등록하세요 (등록하는 순간부터 앞으로만 셉니다):")
        print(f"  python3 scan.py add {kept[0]['addr']} 별명")
        print("\n등록 전에 디뱅크에서 눈으로 확인하는 것도 좋습니다:")
        print(f"  https://debank.com/profile/{kept[0]['addr']}")


if __name__ == "__main__":
    main()
