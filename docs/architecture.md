# 아키텍처 문서

## 시스템 개요

Discord Q&A 자동화 봇 v2. Discord 질문 → 의미 기반 중복 검사 → 신규 질문 AI 답변 생성 → Notion 아카이빙을 자동화한다.

---

## 컴포넌트 구성

```
┌──────────────────────────────────────────────────────────┐
│                       Discord                             │
│          사용자가 !질문 <내용> 입력                         │
└───────────────────────┬──────────────────────────────────┘
                        │ HTTP POST
                        ▼
┌──────────────────────────────────────────────────────────┐
│  bot.py  (discord.py)                                     │
│  - on_message 이벤트 수신                                  │
│  - !질문 명령어 파싱                                        │
│  - Django API 호출 (aiohttp)                              │
│  - 응답을 Discord에 relay                                  │
└───────────────────────┬──────────────────────────────────┘
                        │ HTTP POST /archiver/qna/
                        ▼
┌──────────────────────────────────────────────────────────┐
│  views.py  (DRF APIView)                                  │
│  - 입력값 검증                                              │
│  - QnAService 호출                                         │
│  - 예외 → HTTP 상태코드 매핑                                │
└───────────────────────┬──────────────────────────────────┘
                        │
                        ▼
┌──────────────────────────────────────────────────────────┐
│  services.py  (QnAService)                                │
│  ┌────────────────┐  ┌───────────────────────────────┐   │
│  │check_similarity│  │   process_question_flow        │   │
│  │                │  │                               │   │
│  │  임베딩 생성    │  │  1. 임베딩 생성 (1회)           │   │
│  │  cosine 거리   │  │  2. retrieve_context (RAG)    │   │
│  │  검색 (< 0.2) │  │  3. Gemini 답변 생성            │   │
│  │  hit_count ++  │  │  4. QnALog 저장                │   │
│  └────────────────┘  │  5. 임베딩 저장                 │   │
│                      │  6. Notion 업로드               │   │
│                      └───────────────────────────────┘   │
└──────┬──────────────────────────┬────────────────────────┘
       │                          │
       ▼                          ▼
┌─────────────┐          ┌────────────────────────────────┐
│  adapters.py│          │  adapters.py                   │
│             │          │                                │
│ OpenAI      │          │  GeminiAdapter                 │
│ Embedding   │          │  - Gemini 2.5 Flash 호출        │
│ Adapter     │          │  - 프롬프트 생성                 │
│ - embed()   │          │  - 응답 파싱 → QnACreateDTO     │
└──────┬──────┘          └────────────┬───────────────────┘
       │                              │
       ▼                              ▼
┌──────────────────────────────────────────────────────────┐
│  PostgreSQL + pgvector                                    │
│  - QnALog 테이블 (VectorField 포함)                        │
│  - IvfflatIndex (lists=100) for ANN 검색                   │
└──────────────────────────────────────────────────────────┘
                        │
                        ▼ (is_verified=True 저장 시)
┌──────────────────────────────────────────────────────────┐
│  tasks.py  (django-q2)                                    │
│  - Admin에서 is_verified 체크 시 비동기 트리거              │
│  - NotionAdapter.create_qna_page() 호출                   │
└──────────────────────────────────────────────────────────┘
```

---

## 요청 처리 흐름

### 유사 질문 (중복) 경로

```
!질문 입력
    → OpenAI embed(question)          # 1536차원 벡터 생성
    → pgvector CosineDistance 검색    # is_verified=True & distance < 0.2
    → 유사 질문 발견
    → hit_count + 1 저장
    → notion_page_url 반환
    → Discord에 노션 링크 안내
```

### 신규 질문 경로

```
!질문 입력
    → OpenAI embed(question)          # 1회만 생성
    → pgvector CosineDistance 검색    # 유사 없음
    → retrieve_context()              # distance < 0.5, top-3 RAG 컨텍스트 생성
    → Gemini generate_answer()        # 프롬프트 + 컨텍스트 전달
    → QnALog.objects.create()         # title, answer, category, keywords 저장
    → embedding 저장 (별도 save)
    → NotionAdapter.create_qna_page() # 노션 업로드 (실패해도 200 반환)
    → Discord에 AI 답변 안내
```

---

## 레이어 책임 분리

| 레이어 | 파일 | 책임 |
|--------|------|------|
| 진입점 | `bot.py` | Discord 이벤트 수신, API relay |
| API | `views.py` | 입력 검증, 예외 → HTTP 매핑 |
| 비즈니스 | `services.py` | 유사도 검색, 신규 질문 처리 오케스트레이션 |
| 외부 연동 | `adapters.py` | OpenAI / Gemini / Notion API I/O 전담 |
| 모델 | `models.py` | DB 스키마, Admin 저장 hook |
| 비동기 | `tasks.py` | django-q2 Notion 업로드 태스크 |
| DTO | `dto.py` | 레이어 간 데이터 계약 (Pydantic) |

---

## 예외 계층 구조

```
BaseProjectError
├── ValidationError          → HTTP 400 (잘못된 입력)
├── AIResponseParsingError   → HTTP 400 (AI 응답 파싱 실패)
├── LLMServiceError          → HTTP 503 (AI API 장애)
├── NotionAPIError           → 내부 처리 (로그만, 200 반환)
├── SimilarityCheckError     → 내부 처리
└── DatabaseOperationError   → HTTP 500 (DB 저장 실패)
```

Notion 업로드 실패는 서비스 중단 없이 로그만 남긴다.
AI 답변 생성 실패(LLMServiceError)는 503으로 전파되어 재시도를 유도한다.

---

## 임베딩 전략

- **모델**: OpenAI `text-embedding-3-small` (1536차원)
- **중복 판단 임계값**: cosine distance `< 0.2` (check_similarity)
- **RAG 컨텍스트 임계값**: cosine distance `< 0.5` (retrieve_context, top-3)
- **인덱스**: `IvfflatIndex(lists=100)` — ANN 검색으로 대규모 데이터 성능 확보
- **임베딩 계산 최적화**: `process_question_flow` 내에서 임베딩을 1회 생성 후 `retrieve_context`에 재사용

---

## 주요 설계 결정 요약

| 결정 | 문서 |
|------|------|
| pg_trgm → pgvector RAG 전환 | [ADR-001](adr/ADR-001-pgvector-rag-migration.md) |
| 임베딩(OpenAI) / 답변(Gemini) 분리 | [ADR-002](adr/ADR-002-gemini-model-split.md) |
| FastAPI 실험 후 Django 통합 | [ADR-003](adr/ADR-003-django-over-fastapi.md) |
| DTO + Adapter 패턴 도입 | [ADR-004](adr/ADR-004-dto-adapter-pattern.md) |
