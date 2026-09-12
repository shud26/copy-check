# Copy Check — 데모 영상 대본 (약 3분)

**녹화**: `Cmd + Shift + 5` → 화면 전체 또는 브라우저 창 · 마이크 켜기
**규칙**: 2~4분 · 720p 이상 · 배경음악 금지 · **배속 편집하면 실격**

읽다가 틀리면 그냥 멈췄다가 그 문장부터 다시 읽으면 돼.
나중에 그 부분만 잘라내면 된다. 자르는 건 괜찮고, 빠르게 돌리는 것만 안 된다.

미리 열어둘 것: <https://shud26.github.io/copy-check/>

---

## 1. 여는 말 (약 20초)

> **화면**: 공개 페이지 맨 위 (제목이 보이게)

Hi. This is Copy Check.

It answers one question.

Is that wallet worth copying?

*(이게 코피 체크입니다. 질문 하나에 답합니다. 저 지갑, 따라 살 만한가?)*

---

## 2. 문제 (약 45초)

> **화면**: 그대로 두거나 천천히 아래로 스크롤

Copy trading is everywhere. You find a wallet. It looks profitable. You follow it.

But the number you see is usually wrong.

There are three reasons.

First. Gas is ignored. One wallet in my sample looked break even. After gas, ninety nine percent of its loss was gas.

Second. The score is measured on the past. You pick the wallet after you already see the answer.

Third. One lucky trade can carry the whole record.

*(카피 트레이딩은 흔합니다. 지갑을 찾고, 수익이 나 보이고, 따라갑니다. 그런데 그 숫자는 대개 틀렸습니다. 이유가 셋입니다. 가스를 뺐고, 과거로 채점했고, 운 좋은 한 건이 전부일 수 있습니다.)*

---

## 3. 세 가지 규칙 (약 60초)

> **화면**: GitHub README의 "What this tool does instead" 부분

So this tool has three rules.

Rule one. Forward only.

When you register a wallet, the current block is pinned. Trades before that block are thrown away. The clock starts when you find it.

Rule two. Gas is measured, never guessed.

The subgraph reports gas as zero. So I fetch the real receipts over R P C. If a receipt is missing, it stays unknown. I do not fill it with zero. Gas was zero, and we did not get the gas, are different facts.

Rule three. Drop the single best trade. Then look again.

If a wallet only survives with its best trade included, I report it as one hit dependent. Not as a pass.

*(규칙 셋. 하나, 등록 시점부터 앞으로만 센다. 둘, 가스는 재는 것이지 추정하는 게 아니다. 셋, 제일 좋았던 한 건을 빼고 다시 본다.)*

---

## 4. 실제 화면 (약 50초)

> **화면**: 공개 페이지로 돌아가서, 카드들을 천천히 보여주기

Here is the live page.

These five wallets are demo. They are marked demo, because I registered them backwards in time. I show them so you can see the screen working.

These three are real.

I registered them at block twenty five million, nine hundred four thousand, seven hundred twenty seven. That block never changes.

> **화면**: alt-7a7a 카드를 가리키기

Right now they say, not enough data. Ten closed trades. The gate is twenty.

That is the point. The tool does not guess. No evidence, no verdict.

*(데모 다섯 개는 소급 등록이라 데모라고 표시했습니다. 실제 등록은 셋이고 블록을 못박았습니다. 지금은 표본 부족이라 판정을 안 합니다. 근거 없으면 판정하지 않습니다.)*

---

## 5. The Graph (약 25초)

> **화면**: `graph.py` 또는 `fetch.py` 를 에디터로 열어두기

All of this data comes from The Graph.

Every swap is read from the Uniswap v three subgraph, through the gateway.

Without a subgraph, I would need to run my own indexer. With it, one person can score hundreds of wallets in seconds.

*(모든 데이터가 The Graph에서 옵니다. 유니스왑 v3 서브그래프를 게이트웨이로 읽습니다. 서브그래프가 없으면 인덱서를 직접 돌려야 합니다.)*

---

## 6. 닫는 말 (약 15초)

> **화면**: 공개 페이지 맨 위로

It scores every day at ten past ten, by itself.

Thank you for watching.

*(매일 10시 10분에 혼자 채점합니다. 봐주셔서 감사합니다.)*

---

## 읽을 때만 기억할 것

숫자는 천천히. `25,904,727` = twenty five million, nine hundred four thousand, seven hundred twenty seven.

`v3` = v three · `RPC` = R P C 라고 한 글자씩.

빨리 읽지 말 것. 3분이 목표고 4분까지 괜찮다. 2분보다 짧으면 안 된다.

---
---

# 부록: 한국어 연습본

**제출용이 아니다.** 말하는 속도와 화면 넘기는 타이밍을 몸에 익히는 용도다.
위 영어본과 **문장 순서가 같다.** 이걸로 한 번 찍어보고 3분 근처가 나오면, 그대로 영어로 갈아끼우면 된다.

연습 녹화는 나중에 지우면 된다.

## 1. 여는 말

> **화면**: 공개 페이지 맨 위

안녕하세요. 이건 코피 체크입니다.

질문 하나에 답하는 도구예요.

저 지갑, 따라 살 만한가?

## 2. 문제

> **화면**: 그대로 두거나 천천히 스크롤

카피 트레이딩은 흔합니다. 지갑을 하나 찾고, 수익이 나 보이고, 따라갑니다.

그런데 그때 보는 숫자는 대개 틀렸습니다.

이유가 세 가지예요.

첫째. 가스비가 빠져 있습니다. 제가 본 지갑 중에 본전처럼 보이던 게 있었는데, 가스를 빼고 나니 손실의 구십구 퍼센트가 가스였습니다.

둘째. 과거를 놓고 점수를 냅니다. 답을 이미 보고 나서 지갑을 고르는 거예요.

셋째. 운 좋은 한 건이 전체 기록을 다 끌고 갈 수 있습니다.

## 3. 세 가지 규칙

> **화면**: GitHub README의 "What this tool does instead"

그래서 이 도구엔 규칙이 셋 있습니다.

첫째. 앞으로만 셉니다.

지갑을 등록하면 그 시점의 블록을 못박습니다. 그 앞의 거래는 버립니다. 시계는 당신이 그 지갑을 찾은 순간부터 갑니다.

둘째. 가스는 재는 것이지 추정하는 게 아닙니다.

서브그래프는 가스를 영으로 줍니다. 그래서 저는 실제 영수증을 따로 받아옵니다. 영수증이 없으면 모른다고 둡니다. 영으로 채우지 않습니다. 가스가 영이었다는 것과, 가스를 못 받아왔다는 것은 다른 사실이니까요.

셋째. 제일 좋았던 한 건을 빼고 다시 봅니다.

그 한 건이 있어야만 남는 지갑이면, 통과가 아니라 한 방에 기댔다고 적습니다.

## 4. 실제 화면

> **화면**: 공개 페이지, 카드들을 천천히

이게 실제 화면입니다.

이 다섯 개는 데모예요. 과거 시점으로 소급해서 등록한 거라 데모라고 표시해뒀습니다. 화면이 어떻게 도는지 보여드리려고 넣었어요.

이 셋이 진짜입니다.

블록 이천오백구십만 사천칠백이십칠에 등록했습니다. 이 블록은 바뀌지 않습니다.

> **화면**: alt-7a7a 카드 가리키기

지금은 표본 부족이라고 나옵니다. 완결 거래가 열 건인데 관문이 스무 건이거든요.

그게 핵심입니다. 이 도구는 추측하지 않습니다. 근거가 없으면 판정하지 않습니다.

## 5. The Graph

> **화면**: `graph.py` 또는 `fetch.py`

이 데이터는 전부 The Graph에서 옵니다.

모든 스왑을 유니스왑 v3 서브그래프에서 게이트웨이를 통해 읽습니다.

서브그래프가 없었으면 인덱서를 직접 돌려야 했을 겁니다. 서브그래프 덕분에 혼자서도 수백 개 지갑을 몇 초 만에 채점합니다.

## 6. 닫는 말

> **화면**: 공개 페이지 맨 위

매일 열 시 십 분에 혼자 채점합니다.

봐주셔서 감사합니다.
