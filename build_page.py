#!/usr/bin/env python3
"""out/verdicts.json → out/index.html

화면은 판정 결과만 읽는다. 네트워크도 API 키도 없다.
그래서 정적 호스팅에 그대로 올릴 수 있고, 오프라인에서도 열린다.

⚠️ 화면이 숨기지 말아야 할 것
    "성적이 없다"와 "우리가 못 봤다"는 다르다.
    페이지 상한에 걸렸는지, 가스를 못 받았는지, 데모 등록인지를
    카드마다 그대로 표시한다. 좋아 보이게 만드는 게 목적이 아니다.
"""
import html
import json
import pathlib

import icons

OUT = pathlib.Path("out")


def waterfall(net: float, best: float, ex: float) -> str:
    """최대 1건을 빼면 어떻게 되는지 막대 세 개로.

    ⚠️ 이 도구의 주장이 여기 다 들어 있다. 심사위원이 4분 영상에서
       표 다섯 줄을 읽을 리 없다. **0선을 넘어가는 막대 하나**면 3초에 끝난다.

    왼쪽  가스 뺀 뒤 (지금 성적)
    가운데 빠지는 한 건  ← 항상 아래로. 빼는 것이므로
    오른쪽 남은 것       ← 여기가 0선 아래면 '한 방 의존'

    ⚠️ 0선은 그림 한가운데가 아니라 값의 범위에 따라 움직인다.
       전부 음수인 지갑에서 막대가 위에 뜨면 거짓말이 된다(2026-09-03 수정).
    """
    vals = [net, -abs(best), ex]
    hi = max(max(vals), 0.0)
    lo = min(min(vals), 0.0)
    span = (hi - lo) or 1e-12

    H, TOP, BOT = 46.0, 6.0, 16.0     # 그림 높이 · 위아래 여백
    zero = TOP + (hi / span) * H      # 0선의 y좌표

    def bar(x, v, color, w=54):
        y = TOP + ((hi - v) / span) * H if v >= 0 else zero
        ht = max(2.0, abs(v) / span * H)
        return (f'<rect x="{x}" y="{y:.1f}" width="{w}" height="{ht:.1f}" '
                f'rx="2" fill="var({color})" opacity=".72"/>')

    ty = H + TOP + 12
    return f'''<svg viewBox="0 0 200 {H+TOP+BOT:.0f}" class="wf" role="img"
     aria-label="가스 뺀 뒤 손익에서 최대 1건을 빼면 남는지 보여주는 막대">
  <line x1="0" y1="{zero:.1f}" x2="200" y2="{zero:.1f}"
        stroke="var(--line)" stroke-width="1"/>
  {bar(8, net, "--ok" if net > 0 else "--bad")}
  {bar(73, -abs(best), "--bad")}
  {bar(138, ex, "--ok" if ex > 0 else "--bad")}
  <text x="35" y="{ty:.0f}" font-size="8" fill="var(--mute)" text-anchor="middle">가스 뺀 뒤</text>
  <text x="100" y="{ty:.0f}" font-size="8" fill="var(--mute)" text-anchor="middle">빼는 한 건</text>
  <text x="165" y="{ty:.0f}" font-size="8" fill="var(--mute)" text-anchor="middle">남은 것</text>
</svg>'''


def card(r: dict) -> str:
    v = r.get("verdict", "?")
    n = lambda k: r.get(k, 0) or 0

    # 경고 배지 — 숨기지 않는다
    warn = []
    if r.get("demo"):
        warn.append("데모 등록(소급)")
    if r.get("truncated"):
        warn.append(f"일부만 조회됨")
    if n("gas_skipped_bot"):
        warn.append(f"가스 생략 {n('gas_skipped_bot'):,}건")
    if n("gas_missing"):
        warn.append(f"가스 누락 {n('gas_missing')}건")
    if r.get("error"):
        warn.append("조회 실패")
    warn_html = "".join(
        f'<span class="warn">{html.escape(w)}</span>' for w in warn)

    if r.get("error"):
        return f"""<article class="card" style="{icons.stripe(v)}">
  <div class="top"><b>{html.escape(r['label'])}</b>{icons.badge(v)}</div>
  <div class="addr">{html.escape(r['addr'])}</div>
  <p class="why">{html.escape(r.get('why',''))}</p>
  <div class="warns">{warn_html}</div>
</article>"""

    share = n("best_share")
    bar = min(100.0, share)

    # ⚠️ 가스를 안 받은 지갑은 손익을 숫자로 보여주지 않는다.
    #    0으로 표시하면 "가스가 없었다"로 읽히고, 그러면 봇이 흑자로 보인다.
    #    어제 실측한 그 봇들은 실제로 가스에 100 ETH 넘게 쓰고 있었다.
    #    "없는 것"과 "못 본 것"은 다르다 — 화면이 그걸 흐리면 안 된다.
    no_gas = n("gas_skipped_bot") > 0
    if no_gas:
        rows = f'''<tr><td>가스 빼기 전</td><td class="{'p' if n('realized')>0 else 'm'}">{n('realized'):+.5f}</td></tr>
    <tr><td>가스</td><td class="unk">안 받음</td></tr>
    <tr class="hl"><td>가스 뺀 뒤</td><td class="unk">알 수 없음</td></tr>
    <tr class="key"><td>최대 1건 빼면</td><td class="unk">알 수 없음</td></tr>
    <tr><td>중앙값</td><td class="{'p' if n('median')>0 else 'm'}">{n('median'):+.5f}</td></tr>'''
    else:
        rows = f'''<tr><td>가스 빼기 전</td><td class="{'p' if n('realized')>0 else 'm'}">{n('realized'):+.5f}</td></tr>
    <tr><td>가스</td><td class="dim">−{n('gas'):.5f}</td></tr>
    <tr class="hl"><td>가스 뺀 뒤</td><td class="{'p' if n('net')>0 else 'm'}">{n('net'):+.5f}</td></tr>
    <tr class="key"><td>최대 1건 빼면</td><td class="{'p' if n('net_ex_best')>0 else 'm'}">{n('net_ex_best'):+.5f}</td></tr>
    <tr><td>중앙값</td><td class="{'p' if n('median')>0 else 'm'}">{n('median'):+.5f}</td></tr>'''

    wf = "" if no_gas else waterfall(n("net"), n("best"), n("net_ex_best"))
    return f"""<article class="card" style="{icons.stripe(v)}">
  <div class="top"><b>{html.escape(r['label'])}</b>{icons.badge(v)}</div>
  <div class="addr">{html.escape(r['addr'])}</div>

  <div class="grid">
    <div><span>완결</span><b>{n('closed'):,}</b></div>
    <div><span>승률</span><b>{n('win_rate'):.0f}%</b></div>
    <div><span>토큰</span><b>{n('tokens')}종</b></div>
    <div><span>조회</span><b>{n('seconds')}초</b></div>
  </div>

  <table>{rows}</table>

  {wf}
  {"" if (not share or no_gas) else f'''<div class="sharetxt">최대 1건이 전체 손익의 <b>{share:.0f}%</b></div>'''}

  <p class="why">{html.escape(r.get('why',''))}</p>
  <div class="meta">블록 {n('pinned_block'):,} 고정 · {n('span_blocks'):,}블록 경과
    · 스왑 {n('raw_swaps'):,}→{n('used_swaps'):,}</div>
  <div class="warns">{warn_html}</div>
</article>"""


def build():
    d = json.loads((OUT / "verdicts.json").read_text())
    rs = d["results"]
    order = {"🟢": 0, "🎲": 1, "🔴": 2, "🤖": 3, "⚪": 4, "⏳": 5, "⚠️": 6}
    rs.sort(key=lambda r: (order.get(r.get("verdict", "?")[0], 9), -(r.get("closed") or 0)))

    cnt = {}
    for r in rs:
        cnt[r.get("verdict", "?")] = cnt.get(r.get("verdict", "?"), 0) + 1
    chips = "".join(f'<span class="chipwrap">{icons.badge(k)}'
                    f'<b class="chipnum">{v}</b></span>'
                    for k, v in sorted(cnt.items(),
                                       key=lambda x: order.get(x[0][0], 9)))

    page = f"""<!doctype html>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Copy Check</title>
<style>
:root{{--bg:#fff;--fg:#16181d;--dim:#6b7280;--line:#e5e7eb;--card:#fafafa;
--pos:#0f7b3d;--neg:#c02626;--accent:#2563eb;
--ok:#0f7b3d;--bad:#c02626;--warn:#b45309;--mute:#6b7280}}
@media(prefers-color-scheme:dark){{:root{{--bg:#0f1115;--fg:#e6e8ec;--dim:#8b93a1;
--line:#252932;--card:#161920;--pos:#4ade80;--neg:#f87171;--accent:#60a5fa;
--ok:#4ade80;--bad:#f87171;--warn:#fbbf24;--mute:#8b93a1}}}}
*{{box-sizing:border-box}}
body{{margin:0;padding:30px 18px 70px;background:var(--bg);color:var(--fg);
font:15px/1.7 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}}
.wrap{{max-width:1000px;margin:0 auto}}
h1{{font-size:24px;margin:0 0 4px;letter-spacing:-.02em}}
.sub{{color:var(--dim);font-size:13.5px;margin:0 0 6px;line-height:1.8}}
.chips{{display:flex;gap:16px;flex-wrap:wrap;margin:18px 0 24px;align-items:center}}
.chipwrap{{display:flex;align-items:center;gap:7px}}
.chipnum{{font-size:19px;font-variant-numeric:tabular-nums;letter-spacing:-.02em}}
.cards{{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:14px}}
.card{{background:var(--card);border:1px solid var(--line);border-radius:4px;
padding:15px 17px}}
.top{{display:flex;justify-content:space-between;align-items:center;gap:8px;margin-bottom:2px}}
.top b{{font-size:15.5px}}
.verdict{{display:inline-flex;align-items:center;gap:5px;font-size:11.5px;
font-weight:700;letter-spacing:.03em;padding:3px 9px;border-radius:3px;white-space:nowrap}}
.addr{{font-size:11px;color:var(--dim);font-family:ui-monospace,monospace;
word-break:break-all;margin-bottom:12px}}
.grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:6px;margin-bottom:12px}}
.grid div{{background:var(--bg);border:1px solid var(--line);border-radius:3px;
padding:6px 4px;text-align:center}}
.grid span{{display:block;font-size:10px;color:var(--dim)}}
.grid b{{font-size:14px;font-variant-numeric:tabular-nums}}
table{{width:100%;border-collapse:collapse;font-size:13px;margin-bottom:10px}}
td{{padding:4px 0;font-variant-numeric:tabular-nums}}
td:last-child{{text-align:right}}
tr.hl td{{border-top:1px solid var(--line);padding-top:6px}}
tr.key td{{font-weight:700;background:color-mix(in srgb,var(--accent) 9%,transparent)}}
h1{{font-variant-numeric:tabular-nums}}
.p{{color:var(--pos)}}.m{{color:var(--neg)}}.dim{{color:var(--dim)}}
.unk{{color:var(--dim);font-style:italic;font-size:12px}}
.wf{{width:100%;height:auto;margin:2px 0 4px;display:block}}
.sharetxt{{font-size:11.5px;color:var(--dim);margin:0 0 6px}}
.why{{font-size:12.5px;color:var(--dim);margin:8px 0 6px;line-height:1.7}}
.meta{{font-size:10.5px;color:var(--dim);font-variant-numeric:tabular-nums}}
.warns{{display:flex;gap:5px;flex-wrap:wrap;margin-top:8px}}
.warn{{font-size:10.5px;color:var(--warn);border:1px dashed var(--warn);
border-radius:2px;padding:1px 6px;opacity:.8}}
.note{{font-size:12.5px;color:var(--dim);line-height:1.9;margin-top:34px;
border-top:1px solid var(--line);padding-top:18px}}
.note b{{color:var(--fg)}}
</style>
<div class="wrap">
<h1>Copy Check</h1>
<p class="sub">지갑을 따라 사면 실제로 돈이 되는가 — 등록 시점부터 앞으로만, 가스 포함<br>
{html.escape(d['generated_at'])} · 블록 {d['head_block']:,} · {html.escape(d['chain'])}</p>
<div class="chips">{chips}</div>
<div class="cards">{"".join(card(r) for r in rs)}</div>

<p class="note">
<b>최대 1건 빼면</b> 이 화면의 핵심입니다. 제일 크게 번 매매 하나를 빼고도 남는지 봅니다.
빼면 마이너스가 되는 지갑은 실력이 아니라 <b>한 번을 맞춘 것</b>일 수 있습니다.
승률로도 총손익으로도 이건 안 보입니다.<br>
<b>🤖 봇</b>은 채점하지 않습니다. 하루 20건 넘게 돌리는 상대는 따라 살 수가 없습니다.
어차피 걸러지므로 <b>가스도 받지 않습니다</b> — 그래서 손익을 "알 수 없음"으로 둡니다.
0으로 적으면 가스가 공짜였던 것처럼 보이고, 실제로 그 봇들은 가스에만 수십 ETH를 씁니다.<br>
<b>⚠️ 여기 숫자는 실제보다 좋습니다.</b> 슬리피지와 따라 사는 지연이 반영돼 있지 않습니다.
"데모 등록"은 소급 등록한 것이라 진짜 미래검증이 아닙니다.
</p>
</div>"""
    (OUT / "index.html").write_text(page, encoding="utf-8")
    print(f"→ {OUT/'index.html'}  ({len(rs)}건)")


if __name__ == "__main__":
    build()
