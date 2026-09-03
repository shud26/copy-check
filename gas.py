#!/usr/bin/env python3
"""가스비를 실제 값으로 채운다.

왜 필요한가 (2026-09-02)
    유니스왑 v3 서브그래프의 `transaction.gasUsed` 는 **0으로 채워져 있다.**
    스키마에 필드는 있는데 값이 안 들어온다. 그래서 서브그래프만으로는
    "가스 빼고도 남는가"를 계산할 수 없다.

왜 추정하지 않고 실제 값을 받나
    같은 날 실측한 스왑 5건의 가스가 이랬다.
        0.001457 · 0.000252 · 0.000027 · 0.000043 · 0.000035 ETH
    최대 최소가 **50배 넘게** 차이난다. 블록 baseFee 만으로 뭉개면
    작은 거래의 가스가 과대평가되고, 큰 거래는 과소평가된다.
    카피 검증의 요점이 "가스까지 빼면 남나"인데, 그 가스가 틀리면
    판정 자체가 무의미해진다.

속도
    실측 0.12초/건. 500건이면 약 1분. 캐시가 있으면 두 번째부터는 0초.
    oc8에서 30,000블록을 훑다 25분 만에 죽었던 것과는 성격이 다르다.
    그때는 "이 구간에 뭐가 있나"를 물었고(범위 스캔),
    여기서는 "이 tx의 가스가 얼마냐"를 묻는다(단건 조회). 후자가 훨씬 싸다.

⚠️ 실패하면 0으로 채우지 않는다
    받지 못한 건은 gas=None 으로 두고 개수를 돌려준다.
    0으로 채우면 "가스가 없었다"와 "못 받았다"가 구분되지 않는다.
"""
from __future__ import annotations

import json
import pathlib
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor

UA = {"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"}

# 살아있는 것부터. 하나 막히면 다음으로 넘어간다.
RPCS = [
    "https://ethereum.publicnode.com",
    "https://eth.drpc.org",
]

CACHE = pathlib.Path(".gas_cache.json")


def _load_cache() -> dict:
    if CACHE.exists():
        try:
            return json.loads(CACHE.read_text())
        except Exception:
            return {}
    return {}


def _rpc(method: str, params: list, retries: int = 1):
    last = None
    for attempt in range(retries + 1):
        for url in RPCS:
            try:
                body = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}
                req = urllib.request.Request(url, data=json.dumps(body).encode(), headers=UA)
                r = json.load(urllib.request.urlopen(req, timeout=8))
                if "result" in r and r["result"] is not None:
                    return r["result"]
                last = r.get("error", "result 없음")
            except Exception as e:
                last = e
        if attempt < retries:
            time.sleep(0.8)
    raise RuntimeError(f"모든 RPC 실패: {str(last)[:100]}")


def gas_of(tx_hashes: list[str], verbose: bool = False,
           workers: int = 12) -> tuple[dict, dict]:
    """tx 해시 목록 → {해시: 가스(ETH)}. 캐시 + 병렬.

    ⚠️ 순차로 받으면 건당 0.15초라 3,400건이 8.7분이다(2026-09-03 실측).
       데모 영상 4분 안에 아무것도 못 보여준다. 그래서 병렬로 받는다.

    ⚠️ 워커를 너무 올리면 공개 RPC가 막는다. 12 정도가 안전선이다.
       실패한 건은 0으로 채우지 않고 failed 로만 센다 —
       "가스가 없었다"와 "못 받았다"는 다르다.

    반환: (가스 맵, 통계)
    """
    cache = _load_cache()
    out, stats = {}, {"cached": 0, "fetched": 0, "failed": 0}
    t0 = time.time()
    lock = threading.Lock()

    todo = []
    for h in tx_hashes:
        h = h.lower()
        if h in cache:
            out[h] = cache[h]
            stats["cached"] += 1
        else:
            todo.append(h)

    done = [0]

    def work(h):
        try:
            r = _rpc("eth_getTransactionReceipt", [h])
            g = int(r["gasUsed"], 16) * int(r["effectiveGasPrice"], 16) / 1e18
            with lock:
                out[h] = g
                cache[h] = g
                stats["fetched"] += 1
        except Exception:
            with lock:
                stats["failed"] += 1
        with lock:
            done[0] += 1
            # 200건마다 캐시 저장 — 중간에 죽어도 받아둔 건 안 날아간다
            if done[0] % 200 == 0:
                CACHE.write_text(json.dumps(cache))
                if verbose:
                    print(f"    {done[0]}/{len(todo)} "
                          f"(받음 {stats['fetched']} 실패 {stats['failed']}, "
                          f"{time.time()-t0:.0f}초)", flush=True)

    if todo:
        with ThreadPoolExecutor(max_workers=workers) as ex:
            list(ex.map(work, todo))
        CACHE.write_text(json.dumps(cache))

    stats["seconds"] = round(time.time() - t0, 1)
    return out, stats


def attach(swaps, tx_map: dict, gas_map: dict) -> dict:
    """Swap 목록에 가스를 채워 넣는다.

    tx_map : {(block, ts, token): tx_hash} 형태로 스왑과 해시를 잇는 다리
    반환   : {"filled": n, "missing": n}
    """
    filled = missing = 0
    for s in swaps:
        h = tx_map.get(id(s))
        g = gas_map.get(h) if h else None
        if g is None:
            missing += 1
            continue
        s.gas = g
        filled += 1
    return {"filled": filled, "missing": missing}


if __name__ == "__main__":
    import graph
    SG = "5zvR82QoaXYFyDEKLZ9t6v9adgnptxYpKpSbxtgVENFV"
    d = graph.query(SG, """{
      swaps(first: 20, orderBy: timestamp, orderDirection: desc) {
        transaction { id } } }""")
    hs = [s["transaction"]["id"] for s in d["swaps"]]

    print("1회차 (캐시 없음)")
    g1, s1 = gas_of(hs)
    print(f"  받음 {s1['fetched']} · 캐시 {s1['cached']} · 실패 {s1['failed']} · {s1['seconds']}초")

    print("2회차 (캐시 있음)")
    g2, s2 = gas_of(hs)
    print(f"  받음 {s2['fetched']} · 캐시 {s2['cached']} · 실패 {s2['failed']} · {s2['seconds']}초")

    vals = sorted(g1.values())
    if vals:
        print(f"\n가스 분포 ({len(vals)}건)")
        print(f"  최소 {vals[0]:.6f} · 중앙 {vals[len(vals)//2]:.6f} · 최대 {vals[-1]:.6f} ETH")
        print(f"  최대/최소 = {vals[-1]/vals[0]:.0f}배")
        print("  → 이래서 하나의 추정치로 뭉개면 안 된다")
