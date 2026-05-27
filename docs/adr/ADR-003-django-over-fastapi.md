# ADR-003: FastAPI 실험 후 Django로 통합 결정

## 상태
accepted

## 날짜
2026-05-27

## 맥락

RAG 파이프라인 도입 검토 시 비동기 처리와 AI 워크로드에 유리하다는 이유로
FastAPI로 별도 실험 레포(`django-rag-qna`)를 구성했다.

pgvector 임베딩 저장, RAG 검색 API 1개, 벤치마크 스크립트까지 구현했으나
Discord 연동, Notion 업로드 등 **기존 v1의 전체 파이프라인을 FastAPI로 재구현하는 공수**가 컸다.

## 결정

FastAPI 실험 코드의 RAG 핵심 로직(`embeddings.py`, `rag.py`, `vector_store.py`)만
**Django v1에 포팅**하여 통합한다.

- FastAPI 실험 레포는 벤치마크 근거로 아카이브 유지
- Django ORM + pgvector 확장으로 기존 인프라 재활용
- discord.py, Notion API 연동은 기존 코드 그대로 활용

## 결과

**긍정적**
- 포팅 범위 최소화 (RAG 로직만 이식)
- 기존 Django 인프라 재활용
- 레포 1개로 스토리 일관성 유지

**부정적/트레이드오프**
- FastAPI의 네이티브 비동기 이점 포기
- Django에서 비동기 처리는 별도 설정 필요 (ASGI, async views)
