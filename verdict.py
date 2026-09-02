#!/usr/bin/env python3
"""지갑 하나를 채점한다 — 따라 사면 실제로 돈이 되는가.

이 파일은 **데이터 소스를 모른다.** 스왑 목록을 받아서 판정만 낸다.
서브그래프에서 오든 RPC에서 오든 CSV에서 오든 상관없다.
그래서 API 키 없이도 만들 수 있고, 테스트도 된다.

판정 규칙 (세 가지만 나온다)
    🟢 통과       가스 빼고 남고, 제일 크게 번 한 건을 빼도 남는다
    🎲 한 방 의존  남긴 남는데, 최대 이익 1건 빼면 마이너스
    🔴 탈락       가스 빼면 남는 게 없다
    ⏳ 표본 부족   완결 거래가 관문(기본 20건) 미만

왜 "최대 1건 제외"인가
    승률도 총손익도 이걸 못 잡는다. 실제로 추적하던 지갑 하나가
    완결 68건 · 승률 38% · 가스後 +0.033 ETH 로 통과처럼 보였는데,
    가장 큰 이익 한 건을 빼니 -0.083 ETH 였다.
    따라 하려면 그 한 방에 타 있어야 하는데, 그건 지갑을 고르는 문제가
    아니라 타이밍 문제다. 그래서 별도 판정으로 분리한다.

⚠️ 미래로만 센다
    지갑을 등록한 시점의 블록(pinned_block)보다 **이전 거래는 채점하지 않는다.**
    과거는 고를 수 있어서 성적표가 되지 못한다.
    이 파일은 그 필터를 강제한다 — 호출자가 실수로 과거를 넣어도 걸러낸다.
"""
from __future__ import annotations

import statistics
from collections import deque
from dataclasses import dataclass, field


# ────────────────────────────────────────────── 입력 형태

@dataclass
class Swap:
    """스왑 한 건. 데이터 소스가 이 형태로 맞춰서 넣어준다.

    qty  : 대상 토큰 수량 (양수)
    px   : 기축토큰(ETH 등) 기준 단가
    gas  : 이 거래에 쓴 가스비 (기축토큰 단위, 양수)
    side : "buy" | "sell"
    """
    block: int
    ts: int
    side: str
    token: str
    qty: float
    px: float
    gas: float = 0.0

    @property
    def value(self) -> float:
        return self.qty * self.px


@dataclass
class Trade:
    """완결된 왕복 한 건 (매수 → 매도로 실현된 손익)."""
    token: str
    qty: float
    buy_px: float
    sell_px: float
    open_block: int
    close_block: int
    pnl: float          # 가스 제외 전 실현손익
    gas: float          # 이 왕복에 배분된 가스


# ────────────────────────────────────────────── 채점

@dataclass
class Verdict:
    wallet: str
    chain: str
    closed: int = 0
    wins: int = 0
    realized: float = 0.0
    gas: float = 0.0
    trades: list[Trade] = field(default_factory=list)
    skipped_pre_pin: int = 0     # 등록 이전이라 버린 스왑 수
    unmatched_sells: int = 0     # 살 때를 못 본 매도 (감시 전 취득분)

    # ── 파생값 ───────────────────────────────
    @property
    def net(self) -> float:
        """가스까지 뺀 실현손익."""
        return self.realized - self.gas

    @property
    def win_rate(self) -> float:
        return self.wins / self.closed * 100 if self.closed else 0.0

    @property
    def best(self) -> float:
        """제일 크게 번 한 건. 전부 손실이면 0."""
        pnls = [t.pnl for t in self.trades]
        return max(pnls) if pnls and max(pnls) > 0 else 0.0

    @property
    def net_ex_best(self) -> float:
        """최대 이익 1건을 빼고 다시 계산한 가스後 손익."""
        return (self.realized - self.best) - self.gas

    @property
    def best_share(self) -> float:
        """최대 1건이 전체 실현손익에서 차지하는 비중(%).

        ⚠️ 100%를 넘을 수 있다. 그 한 건이 전체보다 크다는 뜻이고,
           나머지를 합치면 마이너스라는 신호다.
        """
        if self.realized <= 0 or self.best <= 0:
            return 0.0
        return self.best / self.realized * 100

    @property
    def median(self) -> float:
        """중앙값. 이게 마이너스인데 합계가 플러스면 '보통은 잃는다'는 뜻."""
        pnls = [t.pnl for t in self.trades]
        return statistics.median(pnls) if pnls else 0.0

    def judge(self, gate: int = 20) -> tuple[str, str]:
        """(판정, 한 줄 이유)"""
        if self.closed < gate:
            return "⏳ 표본 부족", f"완결 {self.closed}건 (관문 {gate}건)"
        if self.net <= 0:
            return "🔴 탈락", f"가스까지 빼면 {self.net:+.5f}"
        if self.net_ex_best <= 0:
            return "🎲 한 방 의존", (
                f"최대 1건({self.best:+.5f}, 비중 {self.best_share:.0f}%)을 "
                f"빼면 {self.net_ex_best:+.5f}")
        return "🟢 통과", f"최대 1건을 빼도 {self.net_ex_best:+.5f}"


def score(wallet: str, chain: str, swaps: list[Swap], pinned_block: int) -> Verdict:
    """스왑 목록 → 판정.

    FIFO로 왕복을 맞춘다. 먼저 산 물량이 먼저 팔린 것으로 본다.

    ⚠️ pinned_block 이전 스왑은 통째로 버린다. 호출자가 실수로 과거를
       넣어도 여기서 막는다. 버린 개수는 skipped_pre_pin 에 남겨서
       "안 본 것"과 "없는 것"을 구분할 수 있게 한다.
    """
    v = Verdict(wallet=wallet, chain=chain)
    lots: dict[str, deque[list]] = {}     # token -> deque([qty, px, block])

    for s in sorted(swaps, key=lambda x: (x.block, x.ts)):
        if s.block < pinned_block:
            v.skipped_pre_pin += 1
            continue

        v.gas += s.gas

        if s.side == "buy":
            lots.setdefault(s.token, deque()).append([s.qty, s.px, s.block])
            continue

        # 매도 — FIFO로 매칭
        remain = s.qty
        q = lots.get(s.token)
        if not q:
            # 등록 전에 사둔 물량을 파는 것. 손익을 셀 수 없으므로 제외한다.
            v.unmatched_sells += 1
            continue

        while remain > 1e-18 and q:
            lot = q[0]
            take = min(remain, lot[0])
            pnl = take * (s.px - lot[1])
            v.trades.append(Trade(
                token=s.token, qty=take, buy_px=lot[1], sell_px=s.px,
                open_block=lot[2], close_block=s.block, pnl=pnl, gas=0.0))
            v.realized += pnl
            v.closed += 1
            if pnl > 0:
                v.wins += 1
            lot[0] -= take
            remain -= take
            if lot[0] <= 1e-18:
                q.popleft()

        if remain > 1e-18:
            # 판 수량이 산 것보다 많다 = 일부는 감시 전 취득분
            v.unmatched_sells += 1

    return v


# ────────────────────────────────────────────── 출력

def report(vs: list[Verdict], gate: int = 20) -> str:
    out = [f"{'지갑':<12}{'체인':<10}{'완결':>5}{'승률':>6}"
           f"{'가스後':>12}{'최대1건 제외':>14}{'비중':>7}{'중앙값':>11}  판정",
           "-" * 96]
    for v in sorted(vs, key=lambda x: -x.closed):
        j, _ = v.judge(gate)
        out.append(
            f"{v.wallet[:11]:<12}{v.chain:<10}{v.closed:>5}{v.win_rate:>5.0f}%"
            f"{v.net:>+12.5f}{v.net_ex_best:>+14.5f}"
            f"{(f'{v.best_share:.0f}%' if v.best_share else '—'):>7}"
            f"{v.median:>+11.5f}  {j}")
    out.append("-" * 96)
    out.append("⚠️ 슬리피지와 따라 사는 지연은 반영돼 있지 않다. 실제는 이보다 나쁘다.")
    return "\n".join(out)


if __name__ == "__main__":
    # 자체 검증 — 실제 데이터 없이 규칙이 맞게 도는지 확인한다
    def mk(side, qty, px, block, gas=0.001, token="AAA"):
        return Swap(block=block, ts=block, side=side, token=token,
                    qty=qty, px=px, gas=gas)

    print("① 한 방 의존 — 24번 조금씩 잃고 1번 크게 번 지갑")
    sw = []
    b = 1000
    for _ in range(24):                      # 24회 소액 손실
        sw += [mk("buy", 10, 1.00, b), mk("sell", 10, 0.99, b + 1)]; b += 2
    sw += [mk("buy", 10, 1.00, b), mk("sell", 10, 2.00, b + 1)]      # 1회 대박
    v = score("0xTEST1", "base", sw, pinned_block=1000)
    print(report([v]))
    j, why = v.judge()
    print(f"→ {j}: {why}\n")
    assert j == "🎲 한 방 의존", j

    print("② 통과 — 꾸준히 조금씩 버는 지갑")
    sw, b = [], 1000
    for _ in range(25):
        sw += [mk("buy", 10, 1.00, b), mk("sell", 10, 1.05, b + 1)]; b += 2
    v = score("0xTEST2", "base", sw, pinned_block=1000)
    j, why = v.judge()
    print(report([v]))
    print(f"→ {j}: {why}\n")
    assert j == "🟢 통과", j

    print("③ 미래검증 — 등록 이전 거래는 버린다")
    sw = [mk("buy", 10, 1.0, 500), mk("sell", 10, 5.0, 600)]   # 등록 전 대박
    sw += [mk("buy", 10, 1.0, 1000), mk("sell", 10, 0.9, 1001)]  # 등록 후 손실
    v = score("0xTEST3", "base", sw, pinned_block=1000)
    print(f"  버린 스왑 {v.skipped_pre_pin}건 · 완결 {v.closed}건 · 실현 {v.realized:+.5f}")
    assert v.skipped_pre_pin == 2 and v.closed == 1 and v.realized < 0
    print("  ✅ 등록 전 대박이 성적에 안 들어감\n")

    print("④ 감시 전 취득분 매도 — 손익 미산입")
    v = score("0xTEST4", "base", [mk("sell", 10, 5.0, 1000)], pinned_block=1000)
    print(f"  완결 {v.closed}건 · 매칭 실패 매도 {v.unmatched_sells}건")
    assert v.closed == 0 and v.unmatched_sells == 1
    print("  ✅ 살 때를 못 본 매도는 세지 않음\n")

    print("모든 검증 통과 ✅")
