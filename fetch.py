#!/usr/bin/env python3
"""서브그래프 스왑 → verdict.Swap 변환.

이 파일이 하는 일은 딱 하나다. **"토큰이 오갔다"를 "샀다/팔았다"로 번역한다.**

서브그래프는 스왑을 이렇게 준다:
    amount0 = -0.0042   (WBTC 가 지갑에서 나감)
    amount1 = +326.10   (USDT 가 지갑으로 들어옴)

여기엔 "매도"라는 말이 없다. 부호를 보고 우리가 판단해야 한다.
그 판단 기준을 한 곳에 모아둔 게 이 파일이다.

⚠️ 기축토큰(quote)을 무엇으로 볼 것인가
    WBTC/USDT 스왑에서 "WBTC를 팔았다"고 하려면 USDT를 기축으로 봐야 한다.
    그래서 스테이블·WETH 목록을 정해두고, 그쪽을 기축으로 잡는다.
    둘 다 기축이면(USDC/USDT 같은) 환전이라 보고 건너뛴다.
    둘 다 기축이 아니면(밈코인끼리) 어느 쪽이 대상인지 알 수 없어 건너뛴다.
    ⚠️ 건너뛴 개수를 반드시 세서 돌려준다 — "없는 것"과 "못 본 것"은 다르다.

⚠️ 가스는 서브그래프에서 안 온다
    이 서브그래프의 transaction.gasUsed 는 **0으로 채워져 있다**(2026-09-02 확인).
    스키마에 필드는 있는데 값이 없다.
    → 그래서 tx 해시만 여기서 뽑고, 실제 가스는 gas.py 가 RPC로 채운다.

    실측으로 확인된 것: 어떤 지갑은 가스 전 -0.00001(사실상 본전)인데
    가스를 빼면 -0.00197 이었다. **손실의 99%가 가스였다.**
    가스를 안 빼면 판정이 통째로 틀린다.
"""
from __future__ import annotations

import graph
from verdict import Swap

# ⚠️ 기축은 **WETH 하나로 고정한다.** 스테이블을 같이 넣으면 안 된다.
#
#    2026-09-02에 WETH·USDC·USDT·DAI 를 전부 기축으로 뒀더니
#    같은 WBTC 의 단가가 32(ETH 기준)와 77,225(달러 기준)로 섞여 들어왔고,
#    손익을 합산하니 +299,923 ETH(1조원대)라는 말도 안 되는 값이 나왔다.
#
#    oc8에서 이미 배운 것과 같은 실수다 — "단위가 다르면 합산 금지".
#    그때는 체인 간이었고 이번엔 기축 간이었을 뿐이다.
#
#    → 손익을 하나의 숫자로 내려면 기축이 하나여야 한다.
#      스테이블 페어 거래는 채점하지 않고 건너뛴다(개수는 센다).
QUOTE = {
    "0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2": ("WETH", 18),
}

# ⚠️ 중첩 필터(transaction_)를 쓰지 않는다.
#    `where: { transaction_: { blockNumber_gte: N } }` 로 걸면
#    인덱서가 40초를 끌다가 `bad indexers` 로 실패한다(2026-09-02 실측).
#    같은 구간을 `timestamp_gte` 로 거니 **1.7초**에 돌아왔다. 24배 차이다.
#    → 블록이 아니라 시각으로 자르고, 블록 필터는 받아온 뒤에 우리가 건다.
SWAPS_Q = """
query($w: String!, $ts: BigInt!, $skip: Int!) {
  swaps(
    first: 1000, skip: $skip,
    where: { origin: $w, timestamp_gte: $ts }
    orderBy: timestamp, orderDirection: desc
  ) {
    timestamp amountUSD amount0 amount1
    token0 { id symbol decimals }
    token1 { id symbol decimals }
    transaction { id blockNumber }
  }
}"""


def to_swaps(rows: list[dict]) -> tuple[list[Swap], dict, dict]:
    """서브그래프 응답 → Swap 목록.

    반환: (swaps, 건너뛴 사유별 개수, {id(swap): tx해시})
    tx해시를 따로 돌려주는 이유는 가스를 나중에 붙이기 위해서다.
    Swap 자체에 해시를 넣지 않는 건, verdict 가 데이터 출처를 몰라야 하기 때문이다.
    """
    out: list[Swap] = []
    tx_map: dict = {}
    skip = {"둘다기축": 0, "WETH페어아님": 0, "금액0": 0}

    for r in rows:
        t0, t1 = r["token0"], r["token1"]
        a0, a1 = float(r["amount0"]), float(r["amount1"])
        q0 = t0["id"].lower() in QUOTE
        q1 = t1["id"].lower() in QUOTE

        if q0 and q1:
            skip["둘다기축"] += 1
            continue
        if not q0 and not q1:
            # WETH 가 안 낀 거래(스테이블 페어 등). 단위가 달라 합산 불가.
            skip["WETH페어아님"] += 1
            continue

        # 기축이 아닌 쪽이 우리가 채점할 대상 토큰
        if q1:                       # token1 이 기축 → token0 이 대상
            base_amt, quote_amt, token = a0, a1, t0["symbol"]
        else:                        # token0 이 기축 → token1 이 대상
            base_amt, quote_amt, token = a1, a0, t1["symbol"]

        if base_amt == 0 or quote_amt == 0:
            skip["금액0"] += 1
            continue

        # 대상 토큰이 지갑으로 들어왔으면(양수) 매수, 나갔으면(음수) 매도
        side = "buy" if base_amt > 0 else "sell"
        qty = abs(base_amt)
        px = abs(quote_amt) / qty     # 기축 기준 단가

        sw = Swap(
            block=int(r["transaction"]["blockNumber"]),
            ts=int(r["timestamp"]),
            side=side, token=token, qty=qty, px=px,
            gas=0.0,                  # gas.py 가 나중에 채운다
        )
        out.append(sw)
        tx_map[id(sw)] = r["transaction"]["id"].lower()
    return out, skip, tx_map


def fetch(subgraph_id: str, wallet: str, from_block: int, since_ts: int,
          max_pages: int = 10, with_gas: bool = True,
          verbose: bool = False) -> tuple[list[Swap], dict]:
    """지갑 하나의 스왑을 가져온다.

    since_ts   : 서브그래프에 거는 필터 (시각). 넉넉하게 잡는다.
    from_block : 판정에 쓸 실제 기준. 받아온 뒤 여기서 다시 자른다.

    ⚠️ 왜 두 개냐면, 서브그래프는 블록 중첩 필터가 느려서 시각으로 걸고
       (위 SWAPS_Q 주석 참조), 실제 채점 기준은 블록이어야 하기 때문이다.
       블록이 기준인 이유: 등록 시점을 못박는 게 이 도구의 핵심이라
       "몇 시쯤"이 아니라 "정확히 이 블록부터"여야 한다.

    ⚠️ 페이지를 다 못 돌면 그 사실을 meta 에 남긴다. 조용히 잘라내면
       "거래가 적은 지갑"과 "우리가 덜 본 지갑"이 구분되지 않는다.
    """
    # ⚠️ 최신순(desc)으로 받는다. 오름차순으로 받으면 스왑이 아주 많은 지갑에서
    #    페이지 상한에 걸려 **최근 것만 잔뜩 받고 정작 기준 블록 이후가 안 잡힌다.**
    #    2026-09-02에 실제로 1만 건을 받고도 유효 0건이 나왔다.
    #    최신부터 받으면 기준 블록에 닿는 순간 멈출 수 있다.
    rows, page = [], 0
    truncated = False
    while page < max_pages:
        d = graph.query(subgraph_id, SWAPS_Q, {
            "w": wallet.lower(), "ts": str(since_ts), "skip": page * 1000})
        got = d["swaps"]
        rows += got
        if len(got) < 1000:
            break
        # 이번 페이지의 가장 오래된 것이 이미 기준보다 과거면 더 볼 필요 없다
        if int(got[-1]["transaction"]["blockNumber"]) < from_block:
            break
        page += 1
    else:
        truncated = True

    # 서브그래프가 시각으로 잘라줬으니, 정확한 블록 기준은 여기서 건다
    rows = [r for r in rows if int(r["transaction"]["blockNumber"]) >= from_block]

    swaps, skip, tx_map = to_swaps(rows)
    meta = {"raw": len(rows), "used": len(swaps), "skipped": skip,
            "truncated": truncated}

    # ⚠️ 봇으로 판정될 지갑은 가스를 받지 않는다.
    #    어차피 🤖 로 걸러지는데 3,400건 × 0.15초를 쓸 이유가 없다.
    #    스왑 수만으로 미리 알 수 있으므로 여기서 끊는다.
    BOT_HINT = 1000
    if with_gas and len(swaps) >= BOT_HINT:
        meta["gas_skipped_bot"] = len(swaps)
        with_gas = False

    if with_gas and swaps:
        import gas as gasmod
        hashes = list({tx_map[id(s)] for s in swaps})
        gmap, gstat = gasmod.gas_of(hashes, verbose=verbose)
        for s in swaps:
            g = gmap.get(tx_map[id(s)])
            if g is not None:
                s.gas = g
        meta["gas"] = gstat
        meta["gas_missing"] = sum(1 for s in swaps if s.gas == 0.0)

    return swaps, meta


if __name__ == "__main__":
    import sys
    from verdict import score, report

    SG = "5zvR82QoaXYFyDEKLZ9t6v9adgnptxYpKpSbxtgVENFV"

    # 활발한 지갑을 최근 스왑에서 하나 뽑는다
    if len(sys.argv) > 1:
        wallet = sys.argv[1]
    else:
        d = graph.query(SG, "{ swaps(first: 1, orderBy: timestamp, orderDirection: desc) { origin } }")
        wallet = d["swaps"][0]["origin"]

    import datetime as dt
    head = graph.health(SG)
    FROM = head - 200_000          # 데모용으로 과거를 좀 본다 (약 한 달)
    SINCE = int((dt.datetime.now(dt.UTC) - dt.timedelta(days=40)).timestamp())
    print(f"지갑 {wallet}")
    print(f"블록 {FROM:,} ~ {head:,} 구간\n")

    swaps, meta = fetch(SG, wallet, FROM, SINCE, verbose=True)
    print(f"원본 스왑 {meta['raw']}건 → 사용 {meta['used']}건")
    print(f"  건너뜀: {meta['skipped']}")
    if meta["truncated"]:
        print("  ⚠️ 페이지 상한에 걸렸다 — 일부만 본 것")
    if "gas" in meta:
        g = meta["gas"]
        print(f"  가스: 받음 {g['fetched']} · 캐시 {g['cached']} · 실패 {g['failed']} ({g['seconds']}초)")
        if meta["gas_missing"]:
            print(f"  ⚠️ 가스를 못 채운 스왑 {meta['gas_missing']}건")
    print()

    v = score(wallet[:10], "ethereum", swaps, pinned_block=FROM)
    print(report([v], gate=20))
    j, why = v.judge()
    print(f"\n→ {j}: {why}")
    print(f"   총 가스 {v.gas:.6f} ETH · 가스 전 {v.realized:+.5f} → 가스 후 {v.net:+.5f}")
