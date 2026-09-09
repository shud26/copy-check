#!/bin/zsh
# 매일 한 번 등록된 지갑을 다시 채점하고 화면을 새로 만든다.
#
# ⚠️ 이 스크립트는 wallets.json 을 절대 건드리지 않는다.
#    등록 시점(pinned_block)이 바뀌면 이 도구 전체가 무의미해진다.
#    하는 일은 "다시 세는 것"뿐이다.
#
# 자동 푸시는 기본 꺼짐. 켜려면 아래 PUSH=0 을 1 로 바꾼다.
PUSH=0

# ⚠️ launchd 는 형 셸의 PATH 를 안 물려받는다. 그냥 python3 라고 쓰면
#    /usr/bin/python3(3.9)이 잡히고, graph.py 의 `dict | None` 문법에서
#    TypeError 로 죽는다. 터미널에서는 멀쩡히 돌기 때문에 더 헷갈린다.
#    → 인터프리터를 경로로 못박는다.
PY_BIN=/opt/homebrew/bin/python3

# ⚠️ 10:10 에 job 이 뜰 때 맥북이 아직 네트워크를 못 잡은 경우가 있다.
#    (2026-09-08, 09-09 이틀 연속 실패 — "nodename nor servname provided" =
#     DNS 조회 실패. 같은 시각에 .local 이름도 안 잡혔다. 코드 문제가 아니라
#     깨어난 직후 Wi-Fi 가 아직 안 붙은 것.)
#    → 붙을 때까지 기다렸다가 시작한다. 안 붙으면 조용히 죽지 말고 남긴다.
NET_TRIES=20        # 20번 × 60초 = 최대 20분 대기
NET_SLEEP=60

wait_for_net() {
  local i=1
  while [ $i -le $NET_TRIES ]; do
    # 실제로 쓰는 호스트로 확인한다. curl 종료코드 6 = 이름 못 찾음.
    if curl -sS --max-time 10 -o /dev/null "https://gateway.thegraph.com" 2>/dev/null; then
      [ $i -gt 1 ] && echo "  네트워크 붙음 (${i}번째 시도)"
      return 0
    fi
    [ $i -eq 1 ] && echo "  네트워크 대기 중..."
    sleep $NET_SLEEP
    i=$((i + 1))
  done
  return 1
}

cd "$HOME/copy-check" || exit 1
mkdir -p logs
LOG="logs/daily.log"
STAMP=$(date "+%Y-%m-%d %H:%M")

{
  echo "──────── $STAMP ────────"

  wait_for_net || { echo "네트워크 안 붙음 — ${NET_TRIES}분 기다리다 포기"; exit 1; }

  # 한 번 실패해도 회선이 흔들린 것일 수 있으니 2분 뒤 한 번 더 본다.
  if ! "$PY_BIN" scan.py; then
    echo "  1차 채점 실패 — 2분 뒤 재시도"
    sleep 120
    "$PY_BIN" scan.py || { echo "채점 실패"; exit 1; }
  fi
  "$PY_BIN" build_page.py || { echo "화면 생성 실패"; exit 1; }

  # 판정이 처음 나온 지갑이 있으면 눈에 띄게 남긴다.
  # ⏳ 표본 부족에서 벗어나는 날이 이 도구가 처음 말을 하는 날이다.
  "$PY_BIN" - <<'PY'
import json, pathlib
p = pathlib.Path("out/verdicts.json")
d = json.loads(p.read_text())
live = [r for r in d["results"] if not r.get("demo")]
for r in live:
    mark = "  ← 판정 나옴!" if r["verdict"][0] not in "⏳⚠️" else ""
    print(f"  {r['label']:<12} {r['verdict']:<12} 완결 {r.get('closed', 0):>4}{mark}")
PY

  if [ "$PUSH" = "1" ]; then
    export PATH="$HOME/.local/bin:$PATH"
    if ! git diff --quiet -- docs out; then
      git add docs out
      git commit -q -m "자동 채점 $STAMP"
      git push -q origin main && echo "  푸시 완료"
    else
      echo "  변경 없음 — 푸시 생략"
    fi
  fi
} >> "$LOG" 2>&1
