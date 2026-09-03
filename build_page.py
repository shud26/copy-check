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

OUT = pathlib.Path("out")
COLOR = {
    "🟢": ("#0f7b3d", "#dcfce7"),
    "🎲": ("#b45309", "#fef3c7"),
    "🔴": ("#c02626", "#fee2e2"),
    "🤖": ("#4b5563", "#f3f4f6"),
    "⏳": ("#6b7280", "#f9fafb"),
    "⚪": ("#6b7280", "#f3f4f6"),
    "⚠️": ("#c02626", "#fee2e2"),
}


def card(r: dict) -> str:
    v = r.get("verdict", "?")
    fg, bg = COLOR.get(v[0], ("#374151", "#f3f4f6"))
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
        return f"""<article class="card">
  <div class="top"><b>{html.escape(r['label'])}</b>
    <span class="verdict" style="color:{fg};background:{bg}">{html.escape(v)}</span></div>
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

    return f"""<article class="card">
  <div class="top"><b>{html.escape(r['label'])}</b>
    <span class="verdict" style="color:{fg};background:{bg}">{html.escape(v)}</span></div>
  <div class="addr">{html.escape(r['addr'])}</div>

  <div class="grid">
    <div><span>완결</span><b>{n('closed'):,}</b></div>
    <div><span>승률</span><b>{n('win_rate'):.0f}%</b></div>
    <div><span>토큰</span><b>{n('tokens')}종</b></div>
    <div><span>조회</span><b>{n('seconds')}초</b></div>
  </div>

  <table>{rows}</table>

  {"" if (not share or no_gas) else f'''<div class="sharewrap">
    <div class="sharebar"><span style="width:{bar:.0f}%"></span></div>
    <div class="sharetxt">최대 1건이 전체 손익의 <b>{share:.0f}%</b></div>
  </div>'''}

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
    chips = "".join(f'<span class="chip">{html.escape(k)} {v}</span>'
                    for k, v in sorted(cnt.items()))

    page = f"""<!doctype html>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Copy Check</title>
<style>
:root{{--bg:#fff;--fg:#16181d;--dim:#6b7280;--line:#e5e7eb;--card:#fafafa;
--pos:#0f7b3d;--neg:#c02626;--accent:#2563eb}}
@media(prefers-color-scheme:dark){{:root{{--bg:#0f1115;--fg:#e6e8ec;--dim:#8b93a1;
--line:#252932;--card:#161920;--pos:#4ade80;--neg:#f87171;--accent:#60a5fa}}}}
*{{box-sizing:border-box}}
body{{margin:0;padding:30px 18px 70px;background:var(--bg);color:var(--fg);
font:15px/1.7 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}}
.wrap{{max-width:1000px;margin:0 auto}}
h1{{font-size:24px;margin:0 0 4px;letter-spacing:-.02em}}
.sub{{color:var(--dim);font-size:13.5px;margin:0 0 6px;line-height:1.8}}
.chips{{display:flex;gap:7px;flex-wrap:wrap;margin:16px 0 22px}}
.chip{{border:1px solid var(--line);border-radius:20px;padding:3px 12px;font-size:13px}}
.cards{{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:14px}}
.card{{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:16px 17px}}
.top{{display:flex;justify-content:space-between;align-items:center;gap:8px;margin-bottom:2px}}
.top b{{font-size:15.5px}}
.verdict{{font-size:12.5px;font-weight:700;padding:2px 10px;border-radius:20px;white-space:nowrap}}
.addr{{font-size:11px;color:var(--dim);font-family:ui-monospace,monospace;
word-break:break-all;margin-bottom:12px}}
.grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:6px;margin-bottom:12px}}
.grid div{{background:var(--bg);border:1px solid var(--line);border-radius:8px;padding:6px 4px;text-align:center}}
.grid span{{display:block;font-size:10px;color:var(--dim)}}
.grid b{{font-size:14px;font-variant-numeric:tabular-nums}}
table{{width:100%;border-collapse:collapse;font-size:13px;margin-bottom:10px}}
td{{padding:4px 0;font-variant-numeric:tabular-nums}}
td:last-child{{text-align:right}}
tr.hl td{{border-top:1px solid var(--line);padding-top:6px}}
tr.key td{{font-weight:700;background:color-mix(in srgb,var(--accent) 9%,transparent)}}
.p{{color:var(--pos)}}.m{{color:var(--neg)}}.dim{{color:var(--dim)}}
.unk{{color:var(--dim);font-style:italic;font-size:12px}}
.sharewrap{{margin:4px 0 10px}}
.sharebar{{height:5px;background:var(--line);border-radius:3px;overflow:hidden}}
.sharebar span{{display:block;height:100%;background:var(--neg);opacity:.65}}
.sharetxt{{font-size:11.5px;color:var(--dim);margin-top:4px}}
.why{{font-size:12.5px;color:var(--dim);margin:8px 0 6px;line-height:1.7}}
.meta{{font-size:10.5px;color:var(--dim);font-variant-numeric:tabular-nums}}
.warns{{display:flex;gap:5px;flex-wrap:wrap;margin-top:8px}}
.warn{{font-size:10.5px;color:#b45309;background:color-mix(in srgb,#f59e0b 15%,transparent);
border-radius:5px;padding:1px 7px}}
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
