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

# 이더리움 메인넷 기준 기축토큰. 주소는 소문자로.
QUOTE = {
    "0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2": ("WETH", 18),
    "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48": ("USDC", 6),
    "0xdac17f958d2ee523a2206206994597c13d831ec7": ("USDT", 6),
    "0x6b175474e89094c44da98b954eedeac495271d0f": ("DAI", 18),
}

SWAPS_Q = """
query($w: String!, $from: Int!, $skip: Int!) {
  swaps(
    first: 1000, skip: $skip,
    where: { origin: $w, transaction_: { blockNumber_gte: $from } }
    orderBy: timestamp, orderDirection: asc
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
    skip = {"둘다기축": 0, "기축없음": 0, "금액0": 0}

    for r in rows:
        t0, t1 = r["token0"], r["token1"]
        a0, a1 = float(r["amount0"]), float(r["amount1"])
        q0 = t0["id"].lower() in QUOTE
        q1 = t1["id"].lower() in QUOTE

        if q0 and q1:
            skip["둘다기축"] += 1
            continue
        if not q0 and not q1:
            skip["기축없음"] += 1
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


def fetch(subgraph_id: str, wallet: str, from_block: int,
          max_pages: int = 10, with_gas: bool = True) -> tuple[list[Swap], dict]:
    """지갑 하나의 스왑을 from_block 이후로 전부 가져온다.

    ⚠️ 페이지를 다 못 돌면 그 사실을 meta 에 남긴다. 조용히 잘라내면
       "거래가 적은 지갑"과 "우리가 덜 본 지갑"이 구분되지 않는다.
    """
    rows, page = [], 0
    truncated = False
    while page < max_pages:
        d = graph.query(subgraph_id, SWAPS_Q, {
            "w": wallet.lower(), "from": from_block, "skip": page * 1000})
        got = d["swaps"]
        rows += got
        if len(got) < 1000:
            break
        page += 1
    else:
        truncated = True

    swaps, skip, tx_map = to_swaps(rows)
    meta = {"raw": len(rows), "used": len(swaps), "skipped": skip,
            "truncated": truncated}

    if with_gas and swaps:
        import gas as gasmod
        hashes = list({tx_map[id(s)] for s in swaps})
        gmap, gstat = gasmod.gas_of(hashes)
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

    head = graph.health(SG)
    FROM = head - 200_000          # 데모용으로 과거를 좀 본다 (약 한 달)
    print(f"지갑 {wallet}")
    print(f"블록 {FROM:,} ~ {head:,} 구간\n")

    swaps, meta = fetch(SG, wallet, FROM)
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
