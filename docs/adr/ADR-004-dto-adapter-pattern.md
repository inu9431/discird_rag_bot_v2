# ADR-004: DTO + Adapter 패턴 도입

## 상태
accepted

## 날짜
2026-05-27

## 맥락

초기 구현에서는 View가 모델 인스턴스를 직접 dict로 변환하거나, Service가 외부 API 응답 파싱까지 담당하는 구조였다.
이로 인해 두 가지 문제가 발생했다.

1. **타입 불안정**: AI 응답이 문자열로 전달되다 보니 어느 레이어에서 파싱하는지 불명확하고, 런타임에서야 KeyError가 발생했다.
2. **책임 혼재**: Service가 Gemini 응답 파싱 + DB 저장 + Notion 호출을 모두 수행하면서 단일 책임 원칙 위반.

## 결정

**DTO(Data Transfer Object)** 와 **Adapter** 패턴을 도입해 레이어 간 데이터 계약을 명확히 한다.

- **DTO** (`dto.py`): Pydantic 모델로 레이어 간 데이터 형태를 고정한다.
  - `QnACreateDTO`: AI 응답 파싱 결과 및 DB 저장 전 데이터
  - `QnAResponseDTO`: API 응답용 직렬화 데이터

- **Adapter** (`adapters.py`): 외부 API I/O와 DTO 변환을 전담한다.
  - `GeminiAdapter.generate_answer()` → `QnACreateDTO` 반환
  - `qna_model_to_response_dto()` → `QnAResponseDTO` 반환
  - `NotionAdapter.create_qna_page()` → Notion REST API 호출

- **Service** (`services.py`): DTO를 받아 ORM 저장·조회 흐름만 오케스트레이션한다.

## 결과

**긍정적**
- Pydantic 런타임 검증으로 AI 응답 파싱 실패를 `AIResponseParsingError`로 즉시 감지 가능
- Adapter가 `None` 반환 시 Service에서 명확한 에러 처리 가능
- 각 레이어를 독립적으로 Mock할 수 있어 테스트 격리가 쉬워짐

**부정적/트레이드오프**
- DTO 클래스 추가로 코드 파일 수 증가
- 모델 변경 시 DTO, Adapter, 테스트를 함께 수정해야 하는 연동 비용 발생
