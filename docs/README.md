# Docs

## 아키텍처 문서

- [architecture.md](architecture.md) — 컴포넌트 구성, 요청 흐름, 레이어 책임, 예외 계층, 임베딩 전략

## ADR (Architecture Decision Records)

의사결정 배경과 트레이드오프를 기록한다.

| ADR | 제목 | 상태 |
|-----|------|------|
| [ADR-001](adr/ADR-001-pgvector-rag-migration.md) | pg_trgm에서 pgvector + RAG로 전환 | accepted |
| [ADR-002](adr/ADR-002-gemini-model-split.md) | 답변 생성 모델을 Gemini로 분리 | accepted |
| [ADR-003](adr/ADR-003-django-over-fastapi.md) | FastAPI 실험 후 Django로 통합 결정 | accepted |
| [ADR-004](adr/ADR-004-dto-adapter-pattern.md) | DTO + Adapter 패턴 도입 | accepted |
