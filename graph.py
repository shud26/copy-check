#!/usr/bin/env python3
"""The Graph 게이트웨이 클라이언트.

⚠️ User-Agent 를 반드시 보낸다.
   urllib 기본 UA(Python-urllib/3.x)로 보내면 Cloudflare가 봇으로 보고
   `error code: 1010` 으로 잘라버린다. 2026-09-02에 이것 때문에
   "키가 잘못됐나" 하고 한참 헤맸다. 요청이 게이트웨이에 닿지도 못한 것이었다.
"""
import json, os, pathlib, urllib.request, urllib.error

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36")


def load_env(path=".env"):
    p = pathlib.Path(path)
    if not p.exists():
        return
    for ln in p.read_text().splitlines():
        ln = ln.strip()
        if ln and not ln.startswith("#") and "=" in ln:
            k, v = ln.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())


def query(subgraph_id: str, gql: str, variables: dict | None = None,
          key: str | None = None, timeout: int = 30) -> dict:
    """서브그래프에 GraphQL 질의. 실패하면 뭐가 문제인지 말해준다."""
    load_env()
    key = key or os.environ.get("GRAPH_API_KEY")
    if not key:
        raise RuntimeError("GRAPH_API_KEY 가 없습니다 (.env 확인)")

    url = f"https://gateway.thegraph.com/api/{key}/subgraphs/id/{subgraph_id}"
    body = {"query": gql, "variables": variables or {}}
    req = urllib.request.Request(
        url, data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json", "User-Agent": UA})
    try:
        r = json.load(urllib.request.urlopen(req, timeout=timeout))
    except urllib.error.HTTPError as e:
        txt = e.read().decode()[:200]
        if "1010" in txt:
            raise RuntimeError("Cloudflare 차단 — User-Agent 확인") from None
        raise RuntimeError(f"HTTP {e.code}: {txt}") from None

    if "errors" in r:
        msg = r["errors"][0].get("message", "")
        if "API key not found" in msg:
            raise RuntimeError(
                "게이트웨이가 키를 모릅니다. Studio에서 ACTIVE여도 "
                "반영 지연이거나 Security 제한일 수 있습니다.")
        raise RuntimeError(f"쿼리 에러: {msg[:150]}")
    return r["data"]


def health(subgraph_id: str) -> int:
    """서브그래프가 어느 블록까지 색인했는지. 연결 확인용."""
    d = query(subgraph_id, "{ _meta { block { number } } }")
    return d["_meta"]["block"]["number"]


if __name__ == "__main__":
    import sys
    sg = sys.argv[1] if len(sys.argv) > 1 else "5zvR82QoaXYFyDEKLZ9t6v9adgnptxYpKpSbxtgVENFV"
    try:
        print(f"✅ 연결 정상 — 색인 블록 {health(sg):,}")
    except RuntimeError as e:
        print(f"🔴 {e}")
