import pytest
from archiver.models import QnALog

pytestmark = pytest.mark.django_db

class TestnewQuestion:

    def test_new_question_save_response(
            self,api_client, qna_bot_url,
            mock_gemini_adapter, mock_notion_adapter, mock_embedding_adapter):
        response = api_client.post(
            qna_bot_url,
            {"question_text": "pytest 사용법이 뭔가요?"},
        )
        data = response.json()

        assert response.status_code == 200
        assert data["status"] == "new"
        assert data["title"] == "AI가 생성한 테스트 제목"
        assert QnALog.objects.count() == 1

    def test_new_question_save_verify_response(
            self, api_client, qna_bot_url,
            mock_gemini_adapter, mock_notion_adapter, mock_embedding_adapter):
        question = "Django 모델 사용법"
        api_client.post(qna_bot_url, {"question_text": question}, format="json")

        log = QnALog.objects.first()
        assert log.question_text == question
        assert log.title == "AI가 생성한 테스트 제목"
        assert log.notion_page_url == "https://notion.so/fake-page-123"

    def test_Notion_failure_still_returns_200(
            # 실패해도 200 반환
            self, api_client, qna_bot_url,
            mock_gemini_adapter, mock_notion_adapter, mock_embedding_adapter):
        mock_notion_adapter.create_qna_page.side_effect = Exception("Notion 연결 실패")
        response = api_client.post(
            qna_bot_url,
            {"question_text": "Notion 실패 테스트"},
            format="json"
        )

        assert response.status_code == 200
        assert QnALog.objects.count() == 1
        assert QnALog.objects.first().notion_page_url is None

    def test_ai_parsing_failure_returns_400(
            self,api_client, qna_bot_url,
            mock_gemini_adapter, mock_notion_adapter, mock_embedding_adapter
    ):
        mock_gemini_adapter.generate_answer.return_value = None
        # Gemini가 None 반환 시 400응답,  Notion 미 호출
        response = api_client.post(
            qna_bot_url,
            {"question_text": "파싱 실패 질문"},
            format="json"
        )

        assert response.status_code == 400
        assert "AI 응답 형식" in response.json()["error"]
        mock_notion_adapter.create_qna_page.assert_not_called()

    def test_empty_question_returns_400(
            self,api_client, qna_bot_url,
            mock_gemini_adapter, mock_notion_adapter, mock_embedding_adapter
    ):
        # 빈 질문 입력 시 400 응답 Gemini 미 호출
        response = api_client.post(
            qna_bot_url,
            {"question_text": ""},
            format="json"
        )

        assert response.status_code == 400
        mock_gemini_adapter.generate_answer.assert_not_called()
