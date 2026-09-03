#!/usr/bin/env python3
"""등록된 지갑을 채점해서 결과를 파일로 남긴다.

화면(웹)은 이 파일이 만든 JSON만 읽는다. 그래서 화면은 네트워크도
API 키도 필요 없다 — 정적 배포가 가능해진다.

⚠️ 등록 시점(pinned_block)은 wallets.json 에 한 번 적히면 **절대 안 바뀐다.**
   그게 이 도구의 핵심이다. 나중에 성적이 나쁘다고 시점을 옮기면
   그 순간 "과거를 고른 것"이 되어 검증이 무의미해진다.

사용:
    python3 scan.py add 0x지갑주소 [별명]   지갑 등록 (지금 블록에 못박음)
    python3 scan.py                        전부 채점해서 out/verdicts.json 갱신
    python3 scan.py list                   등록 현황
"""
from __future__ import annotations

import datetime as dt
import json
import pathlib
import sys
import time

import fetch
import graph
from verdict import score

SG = "5zvR82QoaXYFyDEKLZ9t6v9adgnptxYpKpSbxtgVENFV"   # Uniswap v3 · Ethereum
CHAIN = "ethereum"

REG = pathlib.Path("wallets.json")
OUT = pathlib.Path("out/verdicts.json")


def load_reg() -> dict:
    return json.loads(REG.read_text()) if REG.exists() else {"wallets": []}


def save_reg(d: dict):
    REG.write_text(json.dumps(d, ensure_ascii=False, indent=2))


def cmd_add(args):
    """지갑 등록. 지금 블록에 못박는다.

    ⚠️ --back N 은 **데모 전용**이다. N블록 전에 등록한 것처럼 만든다.
       진짜 검증이 아니라 화면·영상에 보여줄 게 필요해서 넣은 것이고,
       그렇게 등록된 지갑은 결과에 demo:true 로 표시된다.
       실제 판정에 이걸 쓰면 "과거를 고른 것"이 되어 도구의 전제가 깨진다.
    """
    back = 0
    if "--back" in args:
        i = args.index("--back")
        back = int(args[i + 1])
        args = args[:i] + args[i + 2:]
    if not args:
        print("사용법: scan.py add 0x주소 [별명] [--back 블록수]")
        return
    addr = args[0].lower()
    label = args[1] if len(args) > 1 else addr[:10]
    reg = load_reg()
    if any(w["addr"] == addr for w in reg["wallets"]):
        print(f"이미 등록됨: {addr}")
        return

    head = graph.health(SG)
    pin = head - back
    # 이더리움 블록타임 약 12초
    now = int(time.time()) - back * 12
    reg["wallets"].append({
        "addr": addr, "label": label, "chain": CHAIN,
        "pinned_block": pin,           # ⚠️ 절대 수정 금지
        "pinned_ts": now,
        "pinned_at": dt.datetime.fromtimestamp(now, dt.UTC).strftime("%Y-%m-%d %H:%M UTC"),
        "demo": back > 0,
    })
    save_reg(reg)
    tag = "  ⚠️ 데모(소급 등록)" if back else ""
    print(f"👁 {label} 등록 — 블록 {pin:,} 못박음{tag}")
    print("   이 블록 이후의 거래만 채점된다.")


def cmd_list(args):
    reg = load_reg()
    if not reg["wallets"]:
        print("등록된 지갑이 없습니다. scan.py add 0x… 로 추가하세요.")
        return
    head = graph.health(SG)
    print(f"등록 {len(reg['wallets'])}개 · 현재 블록 {head:,}\n")
    for w in reg["wallets"]:
        span = head - w["pinned_block"]
        print(f"  {w['label']:<12} {w['addr'][:14]}…  "
              f"고정 {w['pinned_block']:>11,}  진행 {span:>8,}블록  ({w['pinned_at']})")


def cmd_scan(args):
    reg = load_reg()
    if not reg["wallets"]:
        print("등록된 지갑이 없습니다.")
        return

    head = graph.health(SG)
    results = []
    print(f"현재 블록 {head:,} · 지갑 {len(reg['wallets'])}개\n")

    for w in reg["wallets"]:
        t = time.time()
        # 서브그래프에는 시각으로 걸고(중첩 필터가 느려서), 블록 필터는 우리가 건다
        since = w["pinned_ts"] - 3600
        try:
            sw, meta = fetch.fetch(SG, w["addr"], w["pinned_block"], since, max_pages=4)
            v = score(w["label"], w["chain"], sw, pinned_block=w["pinned_block"])
            j, why = v.judge(span_blocks=head - w['pinned_block'],
                             gas_known=not meta.get('gas_skipped_bot'))
            results.append({
                "label": w["label"], "addr": w["addr"], "chain": w["chain"],
                "pinned_block": w["pinned_block"], "pinned_at": w["pinned_at"],
                "span_blocks": head - w["pinned_block"],
                "closed": v.closed, "wins": v.wins, "win_rate": round(v.win_rate, 1),
                "realized": v.realized, "gas": v.gas, "net": v.net,
                "net_ex_best": v.net_ex_best, "best": v.best,
                "best_share": round(v.best_share, 1), "median": v.median,
                "tokens": v.tokens,
                "verdict": j, "why": why,
                "demo": w.get("demo", False),
                # ⚠️ "안 본 것"을 숨기지 않는다
                "raw_swaps": meta["raw"], "used_swaps": meta["used"],
                "skipped": meta["skipped"],
                "truncated": meta["truncated"],
                "gas_skipped_bot": meta.get("gas_skipped_bot", 0),
                "gas_missing": meta.get("gas_missing", 0),
                "seconds": round(time.time() - t, 1),
                "error": None,
            })
            print(f"  {w['label']:<12} {j:<14} 완결 {v.closed:>4} · {time.time()-t:>5.1f}초", flush=True)
        except Exception as e:
            results.append({"label": w["label"], "addr": w["addr"], "chain": w["chain"],
                            "verdict": "⚠️ 조회 실패", "why": str(e)[:120],
                            "error": str(e)[:200], "closed": 0})
            print(f"  {w['label']:<12} ⚠️ 실패 — {str(e)[:60]}", flush=True)

    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps({
        "generated_at": dt.datetime.now(dt.UTC).strftime("%Y-%m-%d %H:%M UTC"),
        "head_block": head,
        "subgraph": SG,
        "chain": CHAIN,
        "results": results,
    }, ensure_ascii=False, indent=2))
    print(f"\n→ {OUT} ({len(results)}건)")


CMDS = {"add": cmd_add, "list": cmd_list, "scan": cmd_scan}

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "scan"
    if cmd not in CMDS:
        print(__doc__)
        sys.exit(0)
    CMDS[cmd](sys.argv[2:])
