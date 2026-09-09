# DB 스키마

스키마는 이 프로젝트에서 가장 되돌리기 어려운 결정이다. 데이터가 쌓인 뒤에 구조를
바꾸면 과거 데이터를 잃는다.

**변경 시 반드시 사용자 승인을 받는다.**

---

## 설계 결정 3가지

### ① 소스별 테이블을 나누지 않는다

arXiv · GitHub · HF · Blog를 각각 다른 테이블에 넣으면 직관적으로 보이지만,
랭킹과 검색은 **소스를 가로지르는 연산**이다. 테이블이 4개면 모든 쿼리가 4중 UNION이
되고, 소스를 추가할 때마다 쿼리를 전부 수정해야 한다.

→ 공통 필드는 정규화해 단일 `items`에, 소스 고유 정보는 `raw_json`에.

### ② `raw_json`은 반드시 저장한다

API 응답 원문을 통째로 보관한다. 개발하다 보면 "이 필드도 필요했네"가 반드시 생기는데,
원문이 없으면 **과거 데이터를 재구성할 방법이 없다.** arXiv는 과거 날짜 재수집이
번거롭고, GitHub star 수는 그 시점 값을 영원히 복원할 수 없다.

디스크 수백 MB로 되돌릴 수 없는 손실을 막는 거래다.

### ③ 변하는 값은 `items`에 넣지 않는다

stars · forks · downloads · likes는 **시간에 따라 변하는 값**이다. 이것을 `items`
컬럼에 넣고 매일 UPDATE하면 어제 값이 덮어써지고, 트렌드 계산의 근거가 영원히 사라진다.

→ `item_metrics`에 **append-only**로 쌓는다. Phase 3 트렌드 감지의 유일한 데이터
소스이므로 Phase 1부터 반드시 존재해야 한다.

---

## items

```sql
CREATE TABLE IF NOT EXISTS items (
    id              INTEGER PRIMARY KEY,
    source          TEXT NOT NULL,        -- arxiv | github | huggingface | blog
    source_type     TEXT NOT NULL,        -- paper | repo | model | announcement
    external_id     TEXT NOT NULL,        -- arXiv ID, owner/repo, model path, URL
    title           TEXT NOT NULL,
    summary         TEXT,                 -- abstract / description / 본문 발췌
    url             TEXT NOT NULL,
    authors         TEXT,                 -- JSON array
    tags            TEXT,                 -- JSON array (categories, topics, tags)
    published_at    TIMESTAMP,            -- 원본 발행 시각
    collected_at    TIMESTAMP NOT NULL,   -- 우리가 수집한 시각
    raw_json        TEXT NOT NULL,        -- API 원본 응답 전체
    UNIQUE(source, external_id)
);

CREATE INDEX IF NOT EXISTS idx_items_published ON items(published_at DESC);
CREATE INDEX IF NOT EXISTS idx_items_source    ON items(source, published_at DESC);
```

**`UNIQUE(source, external_id)`** — 1차 중복 제거가 DB 레벨에서 공짜로 해결된다.
동일 항목 재수집 시 `INSERT OR IGNORE`로 조용히 무시된다. 의미 기반 중복(같은 기술의
논문·저장소·모델)은 Phase 2의 별도 과제다.

**`published_at` vs `collected_at`** — 오래된 논문을 오늘 수집할 수 있으므로 둘은
다른 의미다. RAG의 시간 필터 질의("최근 3개월")에서 어느 쪽을 기준으로 할지가
달라진다.

**`authors` / `tags`가 TEXT(JSON)인 이유** — 정규화하면 테이블 2개가 더 생긴다.
Phase 1에서 이들로 조인 검색을 하지 않으므로 지금은 과잉이다. 필요해지면 그때 분리한다.

---

## item_metrics

```sql
CREATE TABLE IF NOT EXISTS item_metrics (
    id          INTEGER PRIMARY KEY,
    item_id     INTEGER NOT NULL REFERENCES items(id),
    metric      TEXT NOT NULL,        -- stars | forks | downloads | likes
    value       REAL NOT NULL,
    recorded_at TIMESTAMP NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_metrics_item
    ON item_metrics(item_id, metric, recorded_at);
```

append-only 시계열 테이블. 매일 같은 저장소의 star 수를 **새 행으로 추가**한다.
UPDATE하지 않는다.

이 테이블만 있으면 *"이 저장소의 star가 지난 2주간 어떤 기울기로 늘었나"* 를 언제든
계산할 수 있다.

**Long format을 택한 이유** — metric 이름을 컬럼이 아닌 값으로 저장하면, 지표 종류가
늘어나도 스키마 변경이 필요 없다. (`stars` 컬럼, `forks` 컬럼… 식으로 만들면 지표가
추가될 때마다 ALTER TABLE)

---

## collection_runs

```sql
CREATE TABLE IF NOT EXISTS collection_runs (
    id             INTEGER PRIMARY KEY,
    source         TEXT NOT NULL,
    started_at     TIMESTAMP NOT NULL,
    finished_at    TIMESTAMP,
    status         TEXT NOT NULL,     -- success | partial | failed
    items_fetched  INTEGER DEFAULT 0,
    items_new      INTEGER DEFAULT 0,
    error_message  TEXT
);
```

관측성 테이블. 며칠 뒤 "어제 수집이 왜 적었지?"를 답할 수 있게 해준다.

더 중요하게는 **포트폴리오의 정량 지표를 산출하는 근거**가 된다.
수집 성공률, 일평균 수집량, 신규 비율, 소스별 실패 유형 분포 — 이 테이블 없이는
"안정적으로 동작한다"를 숫자로 증명할 수 없다.

---

## 이후 Phase에서 추가될 테이블

| 테이블 | Phase | 역할 |
|---|---|---|
| `embeddings` | 2 | item_id ↔ 벡터. 모델명·차원을 함께 저장해 임베딩 모델 비교 실험 가능하게 |
| `summaries` | 2 | LLM 요약. 모델·프롬프트 버전·생성 시각 기록 (재현성 + 비용 추적) |
| `scores` | 2 | 일자별 랭킹 점수. 가중치 조정 전후 비교를 위해 과거 점수 보존 |
| `entity_links` | 2+ | paper ↔ repo ↔ model 연결과 신뢰도 |
| `topics` / `topic_stats` | 3 | 토픽 정의와 주차별 활동량 |
| `eval_queries` | 4 | RAG 평가셋. 질문 ↔ 정답 문서 매핑 |

지금 만들지 않는다. 필요해지는 Phase에서 추가한다.
