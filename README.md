# AI 학습 조교 아카이빙 시스템 v2

Discord 질문 수집 → pgvector 의미 기반 중복 검사 → Gemini AI 답변 생성 → Notion 자동 아카이빙을 통합 관리하는 Q&A 자동화 봇.

---

## 주요 기능

- **Discord 봇 (`!질문`)**: 실시간 질문 감지 및 AI 자동 답변
- **의미론적 중복 검사**: OpenAI 임베딩 + pgvector 코사인 유사도로 표현이 달라도 동일 의미 질문 감지
- **RAG 기반 답변 생성**: 기존 검증된 Q&A를 컨텍스트로 활용해 Gemini 답변 품질 향상
- **Notion 자동 아카이빙**: 신규 질문 생성 즉시 Notion 데이터베이스에 업로드
- **이미지 분석**: 질문에 첨부된 스크린샷(에러 로그 등)을 분석해 답변에 반영
- **Admin 검수 플로우**: 관리자가 답변 검토 후 `is_verified` 체크 시 django-q2가 Notion 재업로드 처리

---

## 시스템 아키텍처

```
Discord !질문 입력
        │
        ▼
OpenAI text-embedding-3-small (1536차원 벡터 생성)
        │
        ▼
pgvector 코사인 거리 검색 (is_verified=True)
        │
        ├── distance < 0.2 → 유사 질문 발견
        │       └── hit_count + 1 → 기존 Notion 링크 반환
        │
        └── 신규 질문
                │
                ▼
        retrieve_context (distance < 0.5, top-3) — RAG 컨텍스트 구성
                │
                ▼
        Gemini 2.5 Flash 답변 생성
                │
                ▼
        QnALog 저장 + 임베딩 저장
                │
                ▼
        Notion 업로드 (실패해도 200 반환)
```

자세한 컴포넌트 구성 및 레이어 책임은 [docs/architecture.md](docs/architecture.md)를 참고.

---

## 기술 스택

| 구분 | 내용 |
|------|------|
| Framework | Django 6.x + DRF |
| DB | PostgreSQL + pgvector (코사인 유사도) |
| 임베딩 | OpenAI `text-embedding-3-small` (1536차원) |
| 답변 생성 | Gemini 2.5 Flash |
| Discord | discord.py |
| Notion | Notion REST API |
| 비동기 작업 | django-q2 |
| API 문서 | drf-spectacular (Swagger) |
| 패키지 관리 | uv |

---

## 환경변수 설정 (`.env`)

```env
DEBUG=
SECRET_KEY=
DATABASE_URL=postgresql://user:password@host:5432/dbname

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

---

## 개발 환경 세팅

```bash
uv sync
cp .env.example .env
docker compose up -d          # PostgreSQL (pgvector 익스텐션 포함)
uv run python manage.py migrate
uv run python manage.py runserver 8001
uv run python bot.py
```

---

## 테스트

```bash
uv run pytest        # 전체 테스트
uv run pytest -v     # 상세 출력
```

CI는 GitHub Actions에서 PostgreSQL 서비스 컨테이너를 함께 띄워 pytest를 실행한다.

---

## API 문서

로컬 서버 실행 후:
- Swagger UI: `http://localhost:8001/api/docs/`
- ReDoc: `http://localhost:8001/api/redoc/`

---

## CI/CD

| 단계 | 트리거 | 내용 |
|------|--------|------|
| CI | 모든 Push | pytest 실행 (PostgreSQL 컨테이너) |
| CD | main 병합 | Docker 멀티플랫폼 빌드 → Docker Hub 푸시 → EC2 배포 + 자동 마이그레이션 |

### GitHub Secrets

| Key | 설명 |
|-----|------|
| `EC2_HOST` | 배포 대상 EC2 퍼블릭 IP |
| `EC2_KEY` | SSH 접속용 프라이빗 키 |
| `DOCKER_USERNAME` | Docker Hub 계정명 |
| `DOCKER_PASSWORD` | Docker Hub Access Token |
| `SECRET_KEY` | Django 보안 키 |
| `DATABASE_URL` | 운영 DB 접속 주소 |
| `GEMINI_API_KEY` | Google Gemini API 키 |
| `OPENAI_API_KEY` | OpenAI API 키 (임베딩용) |
| `NOTION_TOKEN` | Notion 통합 API 토큰 |

---

## 관련 문서

- [아키텍처](docs/architecture.md)
- [ADR 목록](docs/README.md)
