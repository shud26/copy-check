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

cd "$HOME/copy-check" || exit 1
mkdir -p logs
LOG="logs/daily.log"
STAMP=$(date "+%Y-%m-%d %H:%M")

{
  echo "──────── $STAMP ────────"
  "$PY_BIN" scan.py       || { echo "채점 실패"; exit 1; }
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
