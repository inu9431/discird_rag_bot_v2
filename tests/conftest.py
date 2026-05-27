import pytest
from unittest.mock import MagicMock, patch
from django.urls import reverse
from archiver.services import QnAService

@pytest.fixture
def api_client():
    # 테스트 전용 http 클라이언트
    from rest_framework.test import APIClient
    return APIClient()

@pytest.fixture
def qna_bot_url():
    # url 경로 name으로 가져오기
    return reverse("archiver:qna_bot")

@pytest.fixture
def mock_gemini_adapter():
    # 목데이터로 교체
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
    # 목데이터로 교체
    with patch("archiver.services.NotionAdapter") as MockNotion:
        mock_instance = MockNotion.return_value
        mock_instance.create_qna_page.return_value = "https://notion.so/fake-page-123"
        yield mock_instance

@pytest.fixture
def mock_embedding_adapter():
    # 목데이터로 교체
    with patch("archiver.services.OpenAIEmbeddingAdapter") as MockEmbedding:
        mock_instance = MockEmbedding.return_value
        mock_instance.embed.return_value = [0.1] * 1536
        yield mock_instance

@pytest.fixture
def mock_qna_service():
    # 목데이터로 교체
    with patch.object(QnAService, "__init__", lambda x : None):
        service = QnAService()
        service.gemini = MagicMock()
        service.notion = MagicMock()
        service.embedding = MagicMock()
        service.embedding.embed.return_value = [0.1] * 1536
        yield service
