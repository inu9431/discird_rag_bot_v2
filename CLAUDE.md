# CLAUDE.md

## 프로젝트 개요

Discord Q&A 자동화 봇 v2. 사용자가 Discord에서 질문하면 pgvector 기반 의미론적 중복 검사 후, 신규 질문은 Gemini로 답변 생성 및 Notion에 자동 업로드한다.

v1(`bot`) 대비 변경점: pg_trgm 단순 중복 체크 → pgvector 기반 임베딩 유사도 검색으로 고도화 ([ADR-001](docs/adr/ADR-001-pgvector-rag-migration.md))

## 레포지토리 구조

```
bot/
├── archiver/           # Q&A 저장, 노션 업로드, 유사도 체크 (핵심 앱)
│   ├── models.py       # QnALog 모델 (VectorField 포함)
│   ├── services.py     # 비즈니스 로직 (유사도 검색, 질문 처리 흐름)
│   ├── adapters.py     # 외부 서비스 연동 (Gemini, OpenAI 임베딩, Notion)
│   ├── dto.py          # 데이터 전송 객체
│   ├── tasks.py        # 비동기 작업 (django-q)
│   └── views.py        # DRF API 엔드포인트
├── bot.py              # Discord 봇 엔트리포인트
├── common/
│   ├── constants.py    # 공통 상수 (카테고리 목록 등)
│   └── exceptions.py   # 커스텀 예외
├── config/
│   └── settings.py     # Django 설정
├── docs/
│   └── adr/            # Architecture Decision Records
└── pyproject.toml      # 의존성 (uv)
```

## 핵심 아키텍처

```
Discord 메시지 입력
        ↓
OpenAI 임베딩 생성 (text-embedding-3-small)
        ↓
pgvector 코사인 거리 검색
        ├── 유사 Q&A 있음 (distance < 0.2) → 기존 Notion 링크 반환
        └── 신규 질문
                ↓
        Gemini 2.5 Flash 답변 생성
                ↓
        QnALog 저장 + 임베딩 저장
                ↓
        Notion 업로드
```

## 기술 스택

- **Framework**: Django 6.x + DRF
- **DB**: PostgreSQL + pgvector (코사인 유사도) + pg_trgm
- **임베딩**: OpenAI `text-embedding-3-small` (1536차원)
- **답변 생성**: Gemini 2.5 Flash (`google-generativeai`)
- **Discord**: discord.py
- **Notion**: Notion API (REST)
- **비동기 작업**: django-q2
- **API 문서**: drf-spectacular (Swagger `/api/docs/`)
- **패키지 관리**: uv

## 레이어 규칙

- **services.py**: 비즈니스 로직 전담, 유사도 검색 → 답변 생성 흐름 오케스트레이션
- **adapters.py**: 외부 API 연동만 담당 (`GeminiAdapter`, `OpenAIEmbeddingAdapter`, `NotionAdapter`)
- **bot.py**: Discord 이벤트 수신 → service 호출만
- services는 Django ORM 직접 사용, adapter는 외부 I/O만

## 환경변수 (.env)

```
DEBUG=
SECRET_KEY=
DATABASE_URL=postgresql://...
DISCORD_BOT_TOKEN=
GEMINI_API_KEY=
OPENAI_API_KEY=
NOTION_TOKEN=
NOTION_DB_ID=
NOTION_BOARD_URL=
POSTGRES_USER=
POSTGRES_PASSWORD=
POSTGRES_DB=
```

## 개발 환경 세팅

```bash
uv sync
cp .env.example .env
docker-compose up -d    # PostgreSQL (pgvector 익스텐션 포함)
uv run python manage.py migrate
uv run python bot.py
```

## 테스트 실행

```bash
uv run pytest
uv run pytest -v
```

## API 문서

로컬 서버 실행 후:
- Swagger UI: http://localhost:8001/api/docs/
- ReDoc: http://localhost:8001/api/redoc/

## 관련 레포

- [v1 (pg_trgm 기반)](https://github.com/{username}/bot) - 아카이브
- [RAG 실험 (FastAPI)](https://github.com/{username}/django-rag-qna) - 벤치마크 근거 ([ADR-003](docs/adr/ADR-003-django-over-fastapi.md))
