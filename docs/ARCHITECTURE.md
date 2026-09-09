# 아키텍처

## 파이프라인

```
arXiv    GitHub    HuggingFace    BigTech RSS
   │        │           │              │
   └────────┴─────┬─────┴──────────────┘
                  ▼
         BaseCollector → 정규화된 item
                  ▼
         Cleaning / Normalization
                  ▼
         Deduplication  (ID → URL → semantic)
                  ▼
              Embedding (local)
                  ▼
      ┌───────────┴───────────┐
      ▼                       ▼
Relevance Scoring        Trend Detection
 (profile 유사도)          (시계열 metrics)
      └───────────┬───────────┘
                  ▼
           Final Ranking → Top N
                  ▼
           LLM Summary  (상위 N건만)
                  ▼
                SQLite
                  │
      ┌───────────┴──────┐
      ▼                  ▼
  Dashboard            RAG
                (retrieval + citation)
```

---

## 이 순서가 중요한 이유 — 비용 구조

**LLM 요약이 랭킹 뒤에 위치한다.** 이것이 아키텍처의 핵심 결정이다.

하루 수집량 300건 전부를 LLM에 태우면 월 수십 달러가 나가지만, 랭킹으로 걸러 상위
10~20건만 요약하면 **월 몇 달러**로 끝난다. 비용이 20분의 1이 되면서 품질은 오히려
올라간다 — 볼 가치 없는 항목의 요약은 애초에 필요 없기 때문이다.

같은 이유로 **임베딩은 API가 아니라 로컬 모델**을 쓴다. 300건 임베딩은 CPU에서 수
분이면 끝나고 비용은 0이다. 임베딩은 전량에 적용되는 연산이므로 여기서 API를 쓰면
비용이 선형으로 증가한다.

> 원칙: **전량에 적용되는 연산은 무료로, 비싼 연산은 필터링 뒤에.**

---

## 데이터 소스 4개 레이어

| 레이어 | 성격 | 소스 |
|---|---|---|
| **L1 연구** | 가장 이르지만 노이즈 최다. 실제 기술로 이어질지 불확실 | arXiv (cs.CV, cs.LG, cs.RO, cs.AI) |
| **L2 구현** | 연구가 코드가 된 시점. star 증가 속도 = 커뮤니티 검증 | GitHub Search |
| **L3 배포** | 실제로 쓰이기 시작한 시점. download = 채택률 대리 지표 | Hugging Face Hub |
| **L4 산업** | **연구를 건너뛰고 곧바로 도착.** 논문화되지 않는 변화 | 빅테크 공식 블로그 RSS |

**L4가 왜 필수인가** — GPT-6 Astra(2026-09-03) 같은 발표는 arXiv에도 GitHub에도
Hugging Face에도 올라오지 않는다. L1~L3만 수집하는 시스템은 업계 최대 이슈를 통째로
놓친다. 반대로 뉴스만 보는 사람은 그 밑에서 조용히 성장 중인 연구 흐름을 놓친다.

**기술적 이점** — 빅테크 블로그는 대부분 RSS/Atom이고 arXiv API도 Atom이다. 즉
`feedparser` 하나로 L1과 L4를 같은 파서로 처리할 수 있다. 소스가 6개 늘어나도 새
라이브러리는 필요 없고, 각 소스는 URL과 파싱 규칙만 다른 설정 항목이 된다.

---

## 모듈 구조

```
src/
  collectors/     arxiv.py, github.py, huggingface.py, blog.py, base.py
  database/       schema.py, connection.py
  processing/     (Phase 2)
  ranking/        (Phase 2)
  embeddings/     (Phase 2)
  rag/            (Phase 4)
  dashboard/      app.py
scripts/          collect.py
config/           sources.yaml, profile.yaml
tests/            test_parsers.py
data/             radar.db
logs/
```

빈 폴더는 미리 만들지 않는다. 해당 Phase에서 생성한다.

---

## 실패 격리

파이프라인의 각 단계는 **앞 단계의 부분 실패를 견뎌야 한다.**

- GitHub API가 rate limit에 걸려도 arXiv 수집분은 저장된다
- 블로그 피드 하나가 죽어도 나머지 피드는 수집된다
- LLM API가 죽어도 랭킹까지의 결과는 대시보드에 뜬다

매일 돌아가는 시스템에서 "하나 실패하면 전부 실패"는 곧 방치로 이어지고, 방치는
프로젝트의 죽음이다.

모든 실패는 `collection_runs`에 기록한다. 조용히 실패하는 것이 가장 나쁘다.

---

## 기술 스택과 도입 시점

| 영역 | 선택 | 도입 | 이유 |
|---|---|---|---|
| 언어 | Python 3.11 | P1 | 수집·ML·서빙을 한 언어로 |
| 수집 | requests + feedparser | P1 | arXiv와 블로그가 모두 Atom/RSS |
| DB | SQLite | P1 | 단일 사용자에 서버형 DB는 과잉 |
| 임베딩 | sentence-transformers | P2 | 로컬 CPU 실행, 비용 0, 모델 교체 용이 |
| 벡터 검색 | numpy → FAISS | P2 | 수만 건은 브루트포스로 충분 |
| LLM | 추상 클라이언트 | P2 | 벤더 종속 회피 |
| 대시보드 | Streamlit | P1 | 프론트엔드는 평가 대상이 아님 |
| 스케줄러 | Windows 작업 스케줄러 | P1 | OS 기본 기능, 별도 데몬 불필요 |
| API | FastAPI | P5 | 로직 분리가 필요해진 시점에만 |
| 컨테이너 | Docker | P5 | 재현성 증명용 |

**의도적으로 제외** — LangChain/LlamaIndex(각 단계를 직접 구현하는 것이 목적),
PostgreSQL/pgvector(SQLite 한계를 실제로 관측한 뒤에), 클라우드 인프라(사용자 1명).
