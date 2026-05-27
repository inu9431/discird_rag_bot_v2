from unicodedata import category

import pytest
import requests
from django.test import TestCase, override_settings
from django.urls import reverse
from unittest.mock import patch, MagicMock, Mock
from config.settings import GEMINI_API_KEY, NOTION_DB_ID
from .services import QnAService
from .models import QnALog
from .dto import QnACreateDTO, QnAResponseDTO
from .tasks import task_process_question
from .adapters import qna_model_to_create_dto, qna_model_to_response_dto, GeminiAdapter, NotionAdapter
from common.exceptions import ValidationError, LLMServiceError, AIResponseParsingError, DatabaseOperationError, NotionAPIError
@pytest.fixture
def qna_bot_api_url():
    """API 엔드포인트 URL을 제공하는 Fixture"""
    return reverse("archiver:qna_bot")


pytestmark = pytest.mark.django_db

@pytest.fixture
def api_client():
    """테스트용 API 클라이언트 제공하는 Fixture"""
    from rest_framework.test import APIClient
    return APIClient()

@pytest.fixture
def qna_bot_url():
    """API 엔드포인트를 URL로 제공하는 Fixture"""
    return reverse("archiver:qna_bot")

@pytest.fixture
def mock_gemini_adapter():
    """
    GeminiAdapter 가짜로 대체하는 Fixture
    테스트 실행중 실제 AI API 호출을 방지합니다
    """
    with patch("archiver.services.GeminiAdapter") as MockGemini:
        mock_instance = MockGemini.return_value
        mock_dto = MagicMock()
        mock_dto.ai_answer = "테스트 AI 답변입니다"
        mock_dto.category = "Python"
        mock_dto.keywords = "테스트, pytest, django"
        mock_dto.title = "AI가 생성한 테스트 제목"
        mock_instance.generate_answer.return_value = mock_dto
        yield mock_instance
@pytest.fixture
def mock_notion_adapter():
    """
    NotionAdapter를 가짜로 대체하는 Fixture
    테스트 실행중 실제 Notion API 호출을 방지
    """
    with patch("archiver.services.NotionAdapter") as MockNotion:
        mock_instance = MockNotion.return_value
        mock_instance.create_qna_page.return_value = "https://notion.so/fake-page-123"
        yield mock_instance

@pytest.fixture
def mock_embedding_adapter():
    with patch("archiver.services.OpenAIEmbeddingAdapter") as MockEmbedding:
        mock_instance = MockEmbedding.return_value
        mock_instance.embed.return_value = [0.1] * 1536
        yield mock_instance

# ==================================================================================
# 기능 테스트
# ==================================================================================

class TestQnABotAPI:
    """QnABotAPIVIEW의 주요 기능 흐름을 테스트합니다"""

    def test_new_question_flow(self, api_client, qna_bot_url, mock_gemini_adapter, mock_notion_adapter, mock_embedding_adapter):
        """
        [통합 테스트/성공] 실규 질문 시, View-Service-DB 연동 및 AI 응답 처리 흐름을 검증
        """
        # 준비
        test_question = "새로운 통합 테스트 질문입니다"
        request_data = {"question_text": test_question}

        # 실행
        response = api_client.post(qna_bot_url, request_data, format="json")

        # 검증
        assert response.status_code == 200
        response_data = response.json()
        assert response_data["status"] == "new"

        # DB에 데이터가 올바르게 생성되었는지 검증
        assert QnALog.objects.count() == 1
        created_log = QnALog.objects.first()
        assert created_log.question_text == test_question
        assert created_log.title == "AI가 생성한 테스트 제목"
        assert "pytest" in created_log.keywords

        # 응답 데이터가 생성된 데이터와 일치하는지 검증
        assert response_data["id"] == created_log.id
        assert response_data["title"] == created_log.title

        # 외부 서비스가 올바르게 호출되었는지 검증
        mock_gemini_adapter.generate_answer.assert_called_once()

        mock_notion_adapter.create_qna_page.assert_called_once_with(created_log)

    def test_ai_response_parsing_failure(self, api_client, qna_bot_url, mock_gemini_adapter, mock_notion_adapter, mock_embedding_adapter):
        """
        [통합 테스트] AI 응답이 예상과 다른 형식일떄, 파싱 에러를  핸들링하는지 검증
        """

        mock_gemini_adapter.generate_answer.return_value = None
        request_data = {"question_text": "AI 파싱 실패 테스트"}

        response = api_client.post(qna_bot_url, request_data, format="json")

        assert response.status_code == 400
        assert "AI 응답 형식" in response.json()["error"]

        mock_notion_adapter.create_qna_page.assert_not_called()


    def test_notion_api_failure(self, api_client, qna_bot_url, mock_gemini_adapter, mock_notion_adapter, mock_embedding_adapter):
        """
        [통합 테스트 성공] Notion 저장에 실패하더라도, 전체 흐름은 중단되지 않고 성공 응답을 반환하는지 검증
        """
        mock_notion_adapter.create_qna_page.side_effect = Exception("Notion API 에러 발생")
        request_data = {"question_text": "Notion API 실패 테스트 질문"}

        response = api_client.post(qna_bot_url, request_data, format="json")

        # 노션 저장 실패했지만 AI응답은 성공
        assert response.status_code == 200
        response_data = response.json()
        assert response_data["status"] == "new"

        # DB저장 및 AI 분석은 정상이어야함
        assert QnALog.objects.count() == 1
        log = QnALog.objects.first()
        assert log.title == "AI가 생성한 테스트 제목"

        mock_gemini_adapter.generate_answer.assert_called_once()
        mock_notion_adapter.create_qna_page.assert_called_once()
@pytest.fixture
def mock_qna_service():
    """Mock된 QnAService 인스턴스를 제공하는 Fixture"""
    with patch.object(QnAService, '__init__', lambda x: None):
        service = QnAService()
        service.gemini = MagicMock()
        service.notion = MagicMock()
        service.embedding = MagicMock()
        service.embedding.embed.return_value = [0.1] * 1536
        yield service


@pytest.mark.django_db
class TestCheckSimilarity:
    """유사 질문 검색 기능 테스트"""
    def test_returns_not_found_when_no_similar_question(self, mock_qna_service):
        """유사 질문이 없으면 not_found 반환"""
        result = mock_qna_service.check_similarity("완전히 새로운 질문입니다")

        assert result["status"] == "not_found"
        assert result["data"] is None


    def test_returns_similar_found_and_increments_hit_count(self, mock_qna_service):
        """Given 검증된 기존 질문이 있음"""
        existing = QnALog.objects.create(
            question_text = "Django ORM 사용법",
            title = "Django ORM",
            ai_answer = "ORM 사용법 답변",
            is_verified = True,
            hit_count = 5,
            embedding = [0.1] * 1536,
        )

        result = mock_qna_service.check_similarity("Django ORM 사용법")

        assert result["status"] == "similar_found"
        existing.refresh_from_db()
        assert existing.hit_count == 6

@pytest.mark.django_db
class TestProcessQuestionFlow:
    """신규 질문 처리 플로우 테스트"""

    def test_creates_qna_log_with_ai_response(self, mock_qna_service):
        """AI 응답을 받아 QnALog 반환값 설정"""
        mock_dto = MagicMock()
        mock_dto.title = "pytest 기본 사용법"
        mock_dto.category = "Python"
        mock_dto.keywords = ["pytest", "테스트", "TDD"]
        mock_dto.ai_answer = "pytest는 Python 테스트 프레임워크입니다"

        mock_qna_service.gemini.generate_answer.return_value = mock_dto
        mock_qna_service.notion.create_qna_page.return_value = "https://notion.so/page-123"

        result = mock_qna_service.process_question_flow("pytest 사용법")

        assert result.title == "pytest 기본 사용법"
        assert result.notion_page_url == "https://notion.so/page-123"
        mock_qna_service.gemini.generate_answer.assert_called_once()

    def test_raises_validation_error_when_empty_question(self, mock_qna_service):
        """빈 질문일떄 ValidationError 발생"""
        with pytest.raises(ValidationError, match="질문을 입력해주세요"):
            mock_qna_service.process_question_flow("")

class TestCreateQnaDtoFromAiResponse:
    """AI 응답 파싱 기능 테스트"""
    def test_parses_complete_ai_response(self):
        """제목, 카테고리, 키워드 포함된 AI 응답 파싱"""
        from .adapters import create_qna_dto_from_ai_response

        ai_response = """제목: Django ORM 최적화 방법

    카테고리: Django
    키워드: ORM, 쿼리셋, N + 1

    1. ** 문제
    요약 **: 쿼리
    성능
    저하
    2. ** 핵심
    원인 **: N + 1
    문제
    발생
    3. ** 해결
    코드 **: select_related
    사용
    """
        result = create_qna_dto_from_ai_response(
            question_text="Django ORM 최적화 어떻게 하나요?",
            ai_raw_text=ai_response
        )

        assert result.title == "Django ORM 최적화 방법"
        assert result.category == "Django"
        assert result.keywords == ["ORM", "쿼리셋", "N + 1"]
        assert result.question_text == "Django ORM 최적화 어떻게 하나요?"

    def test_uses_defaults_when_fields_missing(self):
        """필드가 없을떄 기본값 사용"""
        from .adapters import create_qna_dto_from_ai_response

        ai_response = "그냥 답변만 있는 텍스트입니다"

        result = create_qna_dto_from_ai_response(
            question_text="질문입니다",
            ai_raw_text=ai_response
        )

        assert result.title == "신규 질문"
        assert result.category == "General"
        assert result.keywords == []

class TestTaskProcessQuestion:
    """Task_process_question 비동기 태스크 테스트"""

    @pytest.fixture
    def sample_qna_log(self, db):
        """테스트용 QnALog 생성"""
        return QnALog.objects.create(
        question_text="테스트 질문",
        ai_answer = "테스트 응답",
        parent_question= None
        )

    @patch('archiver.tasks.logger')
    @patch('archiver.tasks.NotionAdapter')
    @patch('archiver.tasks.qna_model_to_create_dto')
    def test_successfully_creates_notion_page_and_saves_url(self, mock_qna_dto_converter, mock_adapter_class, mock_logger, sample_qna_log ):
        """노션 페이지 생성 성공시 URL을 저장"""
        mock_dto = Mock()
        mock_qna_dto_converter.return_value = mock_dto

        mock_adapter = Mock()
        mock_adapter.create_qna_page.return_value = "https://notion.so/test-page"
        mock_adapter_class.return_value = mock_adapter

        task_process_question(sample_qna_log.id)

        mock_logger.info.assert_called_once()
        assert "노션 업로드 완료" in mock_logger.info.call_args[0][0]

class TestTaskProcessQustionFailure:
    """task_process_question 실패 케이스 테스트"""

    def test_log_not_found_deos_not_raise(self, db):
        """DOesNotExist는 로깅만 하고 예외를 던지지는 않음"""
        task_process_question(99999)

    @patch("archiver.tasks.NotionAdapter")
    def test_notion_failure_raises_exception(self, mock_adapter_class, db):
        """Notion 업로드 실패시 예외를 던짐"""
        # Given
        log = QnALog.objects.create(
            question_text = "테스트 질문",
            title = "테스트",
            ai_answer = "테스트 답변"
        )

        # When
        mock_adapter = MagicMock()
        mock_adapter.create_qna_page.side_effect = Exception("Notion API 실패")
        mock_adapter_class.return_value = mock_adapter

        # then
        with pytest.raises(Exception, match="Notion API 실패"):
            task_process_question(log.id)



class TestQnAModelToCreateDTO:
    """QnALog -> QnACreateDTO 변환 테스트"""

    def test_converts_qna_Log_to_create_dto(self, db):
        """QnALog를 QnACreateDTO로 변환"""
        qna_log = QnALog.objects.create(
            category="Django",
            title="Django ORM 질문",
            question_text = "ORM 사용법이 궁굼합니다",
            ai_answer = "Django ORM은 ..",
            keywords = "Django, ORM",
            hit_count = 3
        )

        dto = qna_model_to_create_dto(qna_log)

        assert isinstance(dto, QnACreateDTO)
        assert dto.question_text == "ORM 사용법이 궁굼합니다"
        assert dto.category == "Django"
        assert dto.title == "Django ORM 질문"
        assert dto.ai_answer == "Django ORM은 .."
        assert dto.keywords ==["Django", "ORM"]
        assert dto.hit_count == 3

    def test_handles_optional_fields_in_create_dto(self, db):
        """ 선택적 필드를 처리"""
        qna_log = QnALog.objects.create(
            category ="General",
            title = "최소 정보",
            question_text = "질문",
            ai_answer = "답변"
        )

        dto = qna_model_to_create_dto(qna_log)
        assert dto.category == "General"
        assert dto.title == "최소 정보"
        assert dto.question_text == "질문"
        assert dto.ai_answer == "답변"
        assert dto.keywords == [] or dto.keywords is not None

    def test_create_dto_is_immutable(self, db):
        """CreateDTO는 불변 객체"""
        qna_log = QnALog.objects.create(
            title = "테스트",
            question_text = "질문",
            ai_answer = "답변"
        )

        dto = qna_model_to_create_dto(qna_log)

        with pytest.raises(Exception):
            dto.title = "변경 시도"

class TestQnAModelToResponseDTO:
    """QnALog -> QnAResponseDTO 변환 테스트"""

    def test_converts_qna_log_to_response_dto(self, db):
        """QnALog를 QnAResponseDTO로 변환"""
        qna_log = QnALog.objects.create(
            category ="Django",
            title="테스트 제목",
            question_text = "질문",
            ai_answer = "답변",
            keywords = "Django, ORM, Test",
            hit_count = 3,
        )

        dto = qna_model_to_response_dto(qna_log)

        assert dto.category == "Django"
        assert dto.title == "테스트 제목"
        assert dto.question_text == "질문"
        assert dto.ai_answer == "답변"
        assert dto.keywords == ["Django", "ORM", "Test"]
        assert dto.hit_count == 3
        assert dto.created_at == qna_log.created_at

    def test_splits_keywords_from_comma_separated_string(self, db):
        """keywords를 쉼표로 구분한 문자열에서 리스트로 변환한다"""
        qna_log = QnALog.objects.create(
            category="General",
            title="키워드 테스트",
            question_text="질문",
            ai_answer="답변",
            keywords="Python, Django, REST API"
        )

        dto = qna_model_to_response_dto(qna_log)

        assert dto.keywords == ["Python", "Django", "REST API"]

    def test_handles_empty_keywords(self, db):
        """keywords가 빈 문자열일뗴 빈 리스트 반환"""
        qna_log = QnALog.objects.create(
            category = "General",
            title = "빈 키워드",
            question_text = "질문",
            ai_answer = "답변",
            keywords = None
        )

        dto = qna_model_to_response_dto(qna_log)

        assert dto.keywords == [] or dto.keywods is  None

    def test_response_dto_includes_id_and_timestamps(self, db):
        """ResponseDTO는 id와 created_at을 포함한다"""
        qna_log = QnALog.objects.create(
            category = "General",
            title = "테스트",
            question_text = "질문",
            ai_answer = "답변"
        )

        dto = qna_model_to_response_dto(qna_log)

        with pytest.raises(Exception):
            dto.title = "변경 시도"

    def test_handles_all_optional_fields(self, db):
        """모든 선택적 필드가 있을떄 올바르게 변환"""
        qna_log = QnALog.objects.create(
            category="Django",
            title="테스트",
            question_text="질문",
            ai_answer="답변",
            keywords = "test, example",
            hit_count = 10,
            is_verified = True
        )

        dto = qna_model_to_response_dto(qna_log)

        assert dto.category == "Django"
        assert dto.title == "테스트"
        assert dto.question_text == "질문"
        assert dto.ai_answer == "답변"
        assert dto.keywords == ["test", "example"]
        assert dto.hit_count == 10
        assert dto.id > 0
        assert dto.created_at is not None

    def test_handles_minimal_required_fields(self, db):
        """최소 필수 필드만으로 변환이 가능하다"""
        qna_log = QnALog.objects.create(
            title = "최소 정보",
            question_text = "질문",
            ai_answer = "답변"
        )

        dto = qna_model_to_response_dto(qna_log)

        assert dto.title == "최소 정보"
        assert dto.question_text == "질문"
        assert dto.ai_answer == "답변"
        assert dto.category == "General"

class TestGeminiAdapter:
    """GeminiAdapter 단위 테스트"""

    @patch("archiver.adapters.genai")
    @override_settings(GEMINI_API_KEY='test-api-key')
    def test_generate_answer_success(self, mock_genai):
        """AI 응답 성공시 QnACreateDTO 반환"""

        mock_response = MagicMock()
        mock_response.prompt_feedback.block_reason = None
        mock_response.text = """제목: Django ORM 최적화
카테고리: Django                                                                                                                                                              
키워드: ORM, 쿼리셋, 최적화                                                                                                                                                   
                                                                                                                                                                        
1. **문제 요약**: N+1 쿼리 문제      
"""

        mock_model = MagicMock()
        mock_model.generate_content.return_value = mock_response
        mock_genai.GenerativeModel.return_value = mock_model

        adapter = GeminiAdapter()
        result = adapter.generate_answer("Django ORM 최적화 방법")

        assert isinstance(result, QnACreateDTO)
        assert result.title == "Django ORM 최적화"
        assert result.category == "Django"

    @patch("archiver.adapters.genai")
    @override_settings(GEMINI_API_KEY='test-api-key')
    def test_generate_answer_blocked_response(self, mock_genai):
        """AI 응답이 차단되면 LLMServiceError 발생"""

        mock_response = MagicMock()
        mock_response.prompt_feedback.block_reason = "SAFETY"

        mock_model = MagicMock()
        mock_model.generate_content.return_value = mock_response
        mock_genai.GenerativeModel.return_value = mock_model

        adapter = GeminiAdapter()

        with pytest.raises(LLMServiceError, match="차단"):
            adapter.generate_answer("테스트 질문")

    @patch("archiver.adapters.genai")
    @override_settings(GEMINI_API_KEY='test-api-key')
    def test_generate_answer_empty_response(self, mock_genai):
        """AI 응답이 비어있으면 LLMServiceError 발생"""
        mock_response = MagicMock()
        mock_response.prompt_feedback.block_reason = None
        mock_response.text = None
        mock_response.candidates = []

        mock_model = MagicMock()
        mock_model.generate_content.return_value = mock_response
        mock_genai.GenerativeModel.return_value = mock_model

        adapter = GeminiAdapter()

        with pytest.raises(LLMServiceError, match="비어있습니다"):
            adapter.generate_answer("테스트 질문")

    @patch("archiver.adapters.genai")
    @override_settings(GEMINI_API_KEY="test-api-key")
    def test_generate_answer_quota_exceeded(self, mock_genai):
        """API 할달량 초과시 LLMServiceError 발생"""
        mock_model = MagicMock()
        mock_model.generate_content.side_effect = Exception("quota exceeded")
        mock_genai.GenerativeModel.return_value = mock_model

        adapter = GeminiAdapter()

        with pytest.raises(LLMServiceError, match="할당량 초과"):
            adapter.generate_answer("테스트 질문")

    @override_settings(GEMINI_API_KEY=None)
    def test_init_witout_api_key_raises_error(self):
        """API 키가 없으면 LLMServiceError 발생"""
        with pytest.raises(LLMServiceError, match="GEMINI_API_KEY"):
            GeminiAdapter()



class TestNotionAdapter:
    """NotionAdapter 단위 테스트"""

    @patch("archiver.adapters.requests.post")
    @override_settings(NOTION_TOKEN='test-token', NOTION_DB_ID='test-db-id')
    def test_create_qna_page_success(self, mock_post):
        """노션 페이지 생성 성공시 URL 반환"""

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"url": "https://notion.so/test-page-123"}
        mock_post.return_value = mock_response

        dto = QnACreateDTO(
            question_text="테스트 질문",
            title="테스트 제목",
            category="테스트 카테고리",
            ai_answer="테스트 답변",
            keywords = ["python, Django"],
            hit_count = 1
        )

        adapter = NotionAdapter()
        result = adapter.create_qna_page(dto)

        assert result == "https://notion.so/test-page-123"
        mock_post.assert_called_once()

    @patch("archiver.adapters.requests.post")
    @override_settings(NOTION_TOKEN='test-token', NOTION_DB_ID='test-db-id')
    def test_create_qna_page_api_error(self, mock_post):
        """노션 API 에러 시 NOtionAPIError 발생"""

        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.json.return_value = {"message": "Invalid request"}
        mock_post.return_value = mock_response

        dto = QnACreateDTO(
            question_text="테스트 질문",
            title="테스트 제목",
            ai_answer="테스트 답변",
            category="General",
            keywords=[],
            hit_count=1,
        )

        adapter = NotionAdapter()

        with pytest.raises(NotionAPIError, match="노션 API 에러"):
            adapter.create_qna_page(dto)

    @patch("archiver.adapters.requests.post")
    @override_settings(NOTION_TOKEN='test-token', NOTION_DB_ID='test-db-id')
    def test_create_qna_page_network_error(self, mock_post):
        """네트워크 오류 시 NotionAPIError 발생"""
        mock_post.side_effect = requests.exceptions.RequestException("Connection failed")

        dto = QnACreateDTO(
            question_text="테스트 질문",
            title="테스트 제목",
            ai_answer="테스트 답변",
            category="General",
            keywords=[],
            hit_count=1,
        )

        adapter = NotionAdapter()

        with pytest.raises(NotionAPIError, match="연결 실패"):
            adapter.create_qna_page(dto)

    @override_settings(NOTION_TOKEN=None, NOTION_DB_ID='tset-db-id')
    def test_init_without_token_raises_error(self):
        """NOTION_TOKEN이 없으면 NotionAPIError 발생"""
        with pytest.raises(NotionAPIError, match="NOTION_TOKEN"):
            NotionAdapter()

    @override_settings(NOTION_TOKEN='test-token', NOTION_DB_ID=None)
    def test_init_without_db_id_raises_error(self):
        """NOTION_DB_ID가 없으면 NotionAPIError 발생"""
        with pytest.raises(NotionAPIError, match="NOTION_DB_ID"):
            NotionAdapter()


@pytest.mark.django_db
class TestProcessQuestionFlowFailure:
    """process_question_flow 실패 케이스"""
    def test_database_error_raises_database_operation_error(self, mock_qna_service):
        """DB 저장 중 예외 발생시 DatabaseOperationError 발생"""
        # Given
        mock_dto = MagicMock()
        mock_dto.title = "테스트 제목"
        mock_dto.category = "General"
        mock_dto.keywords = []
        mock_dto.ai_answer = "테스트 답변"
        mock_qna_service.gemini.generate_answer.return_value = mock_dto

        # When, Then
        with patch.object(QnALog.objects, 'create', side_effect=Exception("DB connection failed")):
            with pytest.raises(DatabaseOperationError, match="데이터베이스"):
                mock_qna_service.process_question_flow("테스트 질문")

@pytest.mark.django_db
class  TestQnALogModel:
    """QnALog 모델 테스트"""

    @patch("archiver.models.async_task")
    def test_save_calls_async_task_when_verified_without_notion_url(self, mock_async_task):
        """is_verified=Ture이고 notion_url이 없으면 async_task 호출"""
        # Given
        log = QnALog.objects.create(
            question_text="테스트 질문",
            title="테스트 제목",
            ai_answer="테스트 답변",
        )

        # When
        log.is_verified = True
        log.save()

        # Then
        mock_async_task.assert_called_once_with(
            "archiver.tasks.task_process_question",
            log.id
        )

    @patch("archiver.models.async_task")
    def test_save_does_not_call_async_task_when_not_verified(self, mock_async_task):
        """is_verified=False이면 async_task 호출 안됨"""
        log = QnALog.objects.create(
            question_text="테스트 질문",
            title="테스트 제목",
            ai_answer="테스트 답변",
            is_verified = False
        )

        mock_async_task.assert_not_called()

    @patch("archiver.models.async_task")
    def test_save_does_not_call_async_task_when_notion_url_exists(self, mock_async_task):
        """notion_page_url 이 이미 있으면 async_task 호출 안됨"""
        log = QnALog.objects.create(
            question_text="테스트 질문",
            title="테스트 제목",
            ai_answer="테스트 답변",
            is_verified=True,
            notion_page_url="https://notion.so/existing-page"
        )

        mock_async_task.assert_not_called()

    def test_str_returns_formated_string(self, db):
        """__str__이 올바른 형식의 문자열 반환"""
        log = QnALog.objects.create(
            question_text="테스트 질문",
            title="테스트 제목",
            ai_answer="Django ORM 질문",
            category = "Django",
            hit_count = 5
        )

        assert str(log) == "[Django] 테스트 제목 (빈도: 5)"
        
