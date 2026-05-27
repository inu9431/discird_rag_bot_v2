import pytest
from common.exceptions import LLMServiceError

pytestmark = pytest.mark.django_db


class TestEdgeCases:

    def test_whitespace_only_question_returns_400(self, api_client, qna_bot_url):
        # 공백만 있는 질문은 strip() 후 빈 문자열 → 400
        response = api_client.post(
            qna_bot_url,
            {"question_text": "   "},
            format="json",
        )

        assert response.status_code == 400
        assert "질문을 입력해주세요" in response.json()["error"]

    def test_llm_service_error_returns_503(
            self, api_client, qna_bot_url,
            mock_embedding_adapter, mock_gemini_adapter, mock_notion_adapter):
        mock_gemini_adapter.generate_answer.side_effect = LLMServiceError("API 할당량 초과")

        response = api_client.post(
            qna_bot_url,
            {"question_text": "테스트 질문"},
            format="json",
        )

        assert response.status_code == 503
        assert "API 할당량 초과" in response.json()["error"]
