🤖 AI 학습 조교 아카이빙 시스템 (v2.5)
디스코드 질문 수집부터 AI 답변 생성, 중복 질문 탐지, 그리고 노션 아카이빙까지 한 번에 관리하는 통합 학습 보조 시스템입니다.

📝 프로젝트 개요
수강생이 디스코드에서 질문을 던지면, Google Gemini 1.5 Flash 모델이 즉시 답변을 제공합니다. 특히 지능형 유사도 판정 엔진을 통해 이미 검증된 정답이 있을 경우 노션 링크를 즉시 안내하여 조교의 업무 효율을 극대화합니다.

🌟 주요 기능
Discord Bot (!질문): 실시간 질문 감지 및 AI 자동 답변 (기존 !분석에서 변경).

하이브리드 처리 아키텍처 (New):

동기(Sync): AI 답변 및 키워드 추출을 웹 서버에서 즉시 처리하여 봇 응답 속도 최적화.

비동기(Async): 느린 노션 API 업로드를 백그라운드 워커(Django-Q)가 전담 처리.

지능형 유사도 판정 (Similarity Check): PostgreSQL pg_trgm 및 GIN 인덱스를 활용해 기존 DB와 대조하여 중복 여부 판정.

질문 빈도(Hit Count) 관리: 검증 완료된 질문에 대해 중복 발생 시 조회수를 카운팅하여 인기 질문 통계 제공.

Image Analysis: 질문에 포함된 스크린샷(에러 로그 등)을 분석하여 답변에 반영.

Django Admin: 관리자가 AI 답변을 수정하고 '검증 완료' 체크 시 노션으로 자동 전송하는 대시보드.

🛠️ 시스템 아키텍처 (Workflow)
질문 수집: 수강생이 디스코드에 !질문 게시.

유사도 검사: AI가 DB(is_verified=True) 내 유사 질문 탐색.

데이터가 있는 경우 (중복): hit_count 증가 → 검증된 노션 URL 즉시 답변 → 종료.

데이터가 없는 경우 (신규): [Web] Gemini AI 분석 → 답변/키워드 즉시 응답 → DB 저장 (hit_count=0).

검수 및 전송: [Admin] 관리자가 내용 확인 후 '검증 완료' 저장 → [Worker] 노션으로 비동기 전송.

💻 기술 스택
Language: Python 3.13+

Framework: Django 5.x (Admin, ORM)

Task Queue: Django-Q2 (Background Worker)

AI: Google Gemini 1.5 Flash

Database: PostgreSQL (pg_trgm extension)

CI/CD: GitHub Actions (Docker Hub, EC2 Auto-Migrate)

🚀 CI/CD 및 배포 (GitHub Actions)본 프로젝트는 GitHub Actions를 활용하여 코드 검증부터 서버 배포까지의 과정을 자동화합니다.1. 주요 워크플로우 (Pipeline)CI (Continuous Integration):코드 푸시 시 PostgreSQL 서비스 컨테이너를 함께 띄워 테스트 환경 구축.uv를 활용한 고속 패키지 설치 및 pytest를 통한 로직 검증.CD (Continuous Deployment):main 브랜치 병합 시 Docker Buildx를 통해 멀티 플랫폼 이미지를 빌드하고 Docker Hub에 푸시.SSH 연동을 통해 EC2 서버에 접속 후 최신 이미지로 컨테이너 갱신.배포 스크립트 내 자동 마이그레이션(migrate) 단계를 포함하여 DB 스키마 동기화.2. 배포 스크립트 핵심 로직 (EC2)배포 시 서버에서는 아래 순서로 작업이 수행됩니다.Bash# 1. 최신 이미지 수신
docker compose pull

# 2. 데이터베이스 스키마 업데이트 (Zero-Downtime 준비)
docker compose run --rm web python manage.py migrate

# 3. 서비스 재시작
docker compose down
docker compose up -d --no-build

# 4. 리소스 정리
docker image prune -f
💡 GitHub Secrets 설정 가이드배포가 정상적으로 작동하려면 GitHub 저장소의 Settings > Secrets > Actions에 아래 변수들이 등록되어 있어야 합니다.Secret KeyDescriptionEC2_HOST배포 대상 EC2 서버의 퍼블릭 IPEC2_KEYSSH 접속용 프라이빗 키 (.pem 내용)DOCKER_USERNAME도커 허브 계정명DOCKER_PASSWORD도커 허브 Access TokenSECRET_KEYDjango 앱 보안 키DATABASE_URL운영용 RDS 접속 주소GEMINI_API_KEYGoogle Gemini API 키NOTION_TOKEN노션 통합 API 토큰

⚙️ 설정 및 실행
환경 변수 설정 (.env)
# Discord Settings
DISCORD_BOT_TOKEN=your_discord_bot_token_here
DISCORD_WEBHOOK_URL=your_discord_webhook_url_here  # 봇 응답 및 알림용 웹훅

# Gemini AI Settings
GEMINI_API_KEY=your_gemini_api_key_here

# Notion Integration
NOTION_TOKEN=your_notion_token_here
NOTION_DB_ID=your_notion_database_id_here
NOTION_BOARD_URL=your_notion_board_public_url_here

# Database Settings (AWS RDS)
DATABASE_URL=postgres://your_user:your_password@your_rds_endpoint:5432/your_db_name

# Docker Hub Credentials
DOCKER_USERNAME=your_docker_hub_username
DOCKER_PASSWORD=your_docker_hub_access_token

# Django Core Settings
DEBUG=False
SECRET_KEY=your_django_secret_key_here
ALLOWED_HOSTS=your_ec2_public_ip_or_domain

🚀 업데이트 노트
(2026-02-02) 아키텍처 개선 및 카테고리 설정 외부화
- **Adapter 책임 강화**: GeminiAdapter가 프롬프트 구성부터 응답 파싱, DTO 반환까지 일괄 처리하도록 개선했습니다.
  - 반환 타입을 `str`에서 `QnACreateDTO`로 변경하여 타입 안정성 확보
  - 프롬프트/파싱 로직의 응집도 향상 (Service → Adapter 이동)
- **카테고리 설정 외부화**: `common/constants.py`로 카테고리를 분리하여 사용자가 쉽게 커스터마이징할 수 있도록 개선했습니다.
  - 모델의 `choices` 제약 제거로 유연한 카테고리 사용 가능
- **코드 품질 개선**: Dead code 제거, 미사용 import 정리, 타입힌트 일관성 확보

(2026-01-16) 코드 구조 리팩토링 및 안정성 강화
- **DTO/Adapter 패턴 도입**: 데이터 처리 흐름의 명확성과 안정성을 위해 DTO(Data Transfer Object)와 Adapter 패턴을 도입했습니다.
  - **DTO**: Pydantic을 사용하여 API 요청/응답 및 내부 데이터 구조를 명세화하고, 런타임 타입 검사를 강화했습니다.
  - **Adapter**: 모델과 DTO 간의 변환 로직을 분리하여 재사용성을 높였습니다.
- **역할과 책임(R&R) 재정의**: View, Service, Task의 역할을 명확히 하여 코드 결합도를 낮추고 유지보수성을 향상시켰습니다.
  - **Service**: 비즈니스 로직의 생성부터 저장까지 모든 흐름을 책임집니다.
  - **View/Task**: Service와 Adapter를 호출하는 '지휘자' 역할에 집중합니다.

(2026-01-14) 성능 및 UX 고도화
아키텍처 최적화: AI 답변 생성 주체를 Worker에서 Web으로 이전하여 봇 응답 대기 시간을 80% 이상 단축했습니다.

비동기 노션 연동: 관리자 페이지 저장 시 발생하는 딜레이를 제거하기 위해 노션 업로드 로직을 Worker로 분리했습니다.

조회수 로직 정교화: 신규 질문은 0부터 시작하며, 검증된 지식 공유 시에만 카운트되도록 로직을 개선했습니다.

배포 자동화 (CD): 배포 시 운영 DB 마이그레이션을 자동으로 수행하는 단계를 추가하여 운영 편의성을 높였습니다.

(2026-01-09) 환경 격리 및 연동
Dockerization: Multi-Container 설정을 통해 개발 및 운영 환경의 일관성을 확보했습니다.

네트워크 최적화: 봇과 서버 간 컨테이너 내부 통신 구조를 확립했습니다.
