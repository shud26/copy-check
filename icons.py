#!/usr/bin/env python3
"""판정 아이콘 — 이모지 대신 쓰는 인라인 SVG.

왜 이모지를 버렸나 (2026-09-03)
    · OS마다 다른 그림이 나온다. 애플 🎲와 윈도우 🎲는 딴 그림이고
      ⚠️ 는 OS가 색을 강제한다. **통제할 수 없는 남의 그림**이다.
    · ⏳ 는 귀엽고 ⚪ 는 무난해 보인다.
      **모른다는 사실이 귀여워지면 안 된다.** 이 도구는 모르는 걸
      숨기지 않는 걸 원칙으로 삼는데, 이모지가 그 원칙을 깎아먹었다.
    · 라이트 전용 배경색을 하드코딩해서 **다크모드에서 흰 알약**이 떴다.

설계 규칙
    · 전부 16×16 그리드, stroke-width 1.5, `currentColor`
      → 색은 CSS 변수가 정한다. 다크모드가 저절로 해결된다.
    · 은유는 하나 — **선과 막대**. 각자 다른 세계에서 온 그림이 아니라
      같은 계측기의 눈금으로 보이게 한다.
    · 세 축으로 구분한다:
        기울기  통과 / 탈락
        밀도    한 방 의존 / 봇
        점선    모르는 것 (표본 부족 · 판정 보류 · 조회 실패)
    · ⚠️ **점선 = 모름.** 확신이 없는 상태는 전부 끊긴 선으로 표시한다.
      색 없이도 "아직 결론이 아니다"가 읽히게 하는 규칙이다.
    · ⚠️ 색만으로 구분하지 않는다. 흑백 스크린샷(심사 자료)이나
      색각이상에서 통과와 탈락이 같아지면 안 되므로 **형태가 두 번째 채널**이다.

⚠️ 아이콘 단독으로 쓰지 않는다. 항상 한글 라벨을 붙인다.
   16px 추상 도형은 이모지만큼 즉각적이지 않다. 보조 수단이다.
"""

_A = ('viewBox="0 0 16 16" width="13" height="13" fill="none" '
      'stroke="currentColor" stroke-width="1.5" stroke-linecap="round" '
      'stroke-linejoin="round" aria-hidden="true"')

ICONS = {
    # 오른쪽 위로 올라가는 선 + 화살촉
    "pass": f'<svg {_A}><path d="M2 12 L6 8 L9 10 L14 4"/>'
            f'<path d="M10.5 4H14v3.5"/></svg>',

    # 평평한 막대들 사이에 하나만 솟음 — 한 건이 전부인 모양
    "lucky": f'<svg {_A}><path d="M2 12v-2M5.5 12v-2.5M9 12V2M12.5 12v-2"/>'
             f'<path d="M1 13.5h14" opacity=".35"/></svg>',

    # 통과의 거울상 — 아래로 내려가는 선
    "fail": f'<svg {_A}><path d="M2 4 L6 8 L9 6 L14 12"/>'
            f'<path d="M10.5 12H14V8.5"/></svg>',

    # 촘촘한 눈금 — 사람이 낼 수 없는 빈도
    "bot": f'<svg {_A}><path d="M2 4v8M4.5 5v6M7 3v10M9.5 5v6M12 4v8M14 6v4"/></svg>',

    # 두 칸만 차고 나머지는 점선 — 아직 덜 쌓임
    "few": f'<svg {_A}><path d="M2 12v-3M5.5 12v-4"/>'
           f'<path d="M9 12v-6M12.5 12v-8" stroke-dasharray="1.5 2"/></svg>',

    # 열린 점선 원 — 닫히지 않은 판정
    "hold": f'<svg {_A}><circle cx="8" cy="8" r="5.5" stroke-dasharray="2 2.5"/></svg>',

    # 끊긴 선 — 데이터가 도달하지 않음
    "error": f'<svg {_A}><path d="M2 8h3.5M10.5 8H14"/>'
             f'<path d="M8 8h.01" stroke-width="2"/></svg>',
}

# 판정 문자열 → (아이콘 키, 색 변수, 점선 여부)
# ⚠️ 점선 여부가 "모르는 것"의 표식이다. 색과 독립적으로 작동해야 한다.
VERDICT = {
    "🟢 통과":      ("pass",  "--ok",   False),
    "🎲 한 방 의존": ("lucky", "--warn", False),
    "🔴 탈락":      ("fail",  "--bad",  False),
    "🤖 봇":       ("bot",   "--mute", False),
    "⏳ 표본 부족":  ("few",   "--mute", True),
    "⚪ 판정 보류":  ("hold",  "--mute", True),
    "⚠️ 조회 실패":  ("error", "--warn", True),
}

LABEL = {
    "🟢 통과": "통과", "🎲 한 방 의존": "한 방 의존", "🔴 탈락": "탈락",
    "🤖 봇": "봇", "⏳ 표본 부족": "표본 부족", "⚪ 판정 보류": "판정 보류",
    "⚠️ 조회 실패": "조회 실패",
}


def badge(verdict: str) -> str:
    """판정 배지 — 아이콘 + 한글 라벨.

    ⚠️ 알약(border-radius 20px)이 아니라 각진 도장이다.
       둥근 알약이 늘어선 화면은 그 자체로 티가 난다.
    """
    key, col, dashed = VERDICT.get(verdict, ("error", "--mute", True))
    label = LABEL.get(verdict, verdict)
    border = "1px dashed" if dashed else "1px solid"
    return (f'<span class="verdict" style="color:var({col});'
            f'border:{border} var({col})">{ICONS[key]}{label}</span>')


def stripe(verdict: str) -> str:
    """카드 왼쪽 띠 — 300px 그리드에서 훑기만 해도 스캔되게."""
    _, col, dashed = VERDICT.get(verdict, ("error", "--mute", True))
    style = "dashed" if dashed else "solid"
    return f"border-left:3px {style} var({col})"


if __name__ == "__main__":
    import pathlib
    cards = "".join(
        f'<div class="c"><div>{badge(v)}</div>'
        f'<code>{v}</code></div>' for v in VERDICT)
    pathlib.Path("out").mkdir(exist_ok=True)
    pathlib.Path("out/_icons.html").write_text(f"""<!doctype html>
<meta charset="utf-8"><title>아이콘 확인</title>
<style>
:root{{--bg:#fff;--fg:#16181d;--line:#e5e7eb;--card:#fafafa;
--ok:#0f7b3d;--bad:#c02626;--warn:#b45309;--mute:#6b7280}}
@media(prefers-color-scheme:dark){{:root{{--bg:#0f1115;--fg:#e6e8ec;--line:#252932;
--card:#161920;--ok:#4ade80;--bad:#f87171;--warn:#fbbf24;--mute:#8b93a1}}}}
body{{background:var(--bg);color:var(--fg);font:15px -apple-system,sans-serif;
padding:30px;margin:0}}
.c{{background:var(--card);border:1px solid var(--line);border-radius:10px;
padding:14px;margin-bottom:8px;display:flex;gap:14px;align-items:center}}
code{{font-size:12px;color:var(--mute)}}
.verdict{{display:inline-flex;align-items:center;gap:5px;font-size:11.5px;
font-weight:700;letter-spacing:.03em;padding:3px 9px;border-radius:3px}}
</style>{cards}""", encoding="utf-8")
    print("→ out/_icons.html  (7종)")
