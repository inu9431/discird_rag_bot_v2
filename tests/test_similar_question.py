import pytest
from archiver.models import QnALog

pytestmark = pytest.mark.django_db


@pytest.fixture
def verified_qna():
    return QnALog.objects.create(
        question_text="파이썬 리스트 사용법",
        title="파이썬 리스트 사용법 정리",
        ai_answer="리스트는 []로 만듭니다",
        category="Python",
        keywords="python, list",
        is_verified=True,
        embedding=[0.1] * 1536,
        notion_page_url="https://notion.so/existing-page",
        hit_count=5,
    )


class TestSimilarQuestion:

    def test_similar_question_returns_similar_found(
            self, api_client, qna_bot_url,
            mock_embedding_adapter, mock_gemini_adapter, mock_notion_adapter,
            verified_qna):
        response = api_client.post(
            qna_bot_url,
            {"question_text": "파이썬 리스트 사용법 알려주세요"},
            format="json",
        )
        data = response.json()

        assert response.status_code == 200
        assert data["status"] == "similar_found"
        assert data["title"] == verified_qna.title

    def test_similar_question_no_new_record_created(
            self, api_client, qna_bot_url,
            mock_embedding_adapter, mock_gemini_adapter, mock_notion_adapter,
            verified_qna):
        api_client.post(
            qna_bot_url,
            {"question_text": "파이썬 리스트 사용법 알려주세요"},
            format="json",
        )

        assert QnALog.objects.count() == 1
        mock_gemini_adapter.generate_answer.assert_not_called()
        mock_notion_adapter.create_qna_page.assert_not_called()

    def test_similar_question_increments_hit_count(
            self, api_client, qna_bot_url,
            mock_embedding_adapter, mock_gemini_adapter, mock_notion_adapter,
            verified_qna):
        api_client.post(
            qna_bot_url,
            {"question_text": "파이썬 리스트 사용법 알려주세요"},
            format="json",
        )

        verified_qna.refresh_from_db()
        assert verified_qna.hit_count == 6

    def test_similar_question_response_includes_notion_url(
            self, api_client, qna_bot_url,
            mock_embedding_adapter, mock_gemini_adapter, mock_notion_adapter,
            verified_qna):
        response = api_client.post(
            qna_bot_url,
            {"question_text": "파이썬 리스트 사용법 알려주세요"},
            format="json",
        )
        data = response.json()

        assert data["status"] == "similar_found"
        assert data["notion_page_url"] == "https://notion.so/existing-page"

    def test_unverified_question_treated_as_new(
            self, api_client, qna_bot_url,
            mock_embedding_adapter, mock_gemini_adapter, mock_notion_adapter):
        # 미검증 질문은 check_similarity 대상 제외 → 신규로 처리
        QnALog.objects.create(
            question_text="파이썬 리스트 사용법",
            title="파이썬 리스트 사용법 정리",
            ai_answer="리스트는 []로 만듭니다",
            category="Python",
            keywords="python, list",
            is_verified=False,
            embedding=[0.1] * 1536,
        )

        response = api_client.post(
            qna_bot_url,
            {"question_text": "파이썬 리스트 사용법"},
            format="json",
        )

        assert response.status_code == 200
        assert response.json()["status"] == "new"
        assert QnALog.objects.count() == 2
