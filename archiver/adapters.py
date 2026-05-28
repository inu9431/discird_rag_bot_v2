import logging
import os
import re
import io
from typing import List, Optional, Union
from common.constants import NOTION_CATEGORIES
from google import genai
from google.genai import types
import requests
from django.conf import settings
from openai import OpenAI
from PIL import Image

from common.exceptions import LLMServiceError, NotionAPIError
from .dto import QnACreateDTO, QnAResponseDTO
from .models import QnALog

logger = logging.getLogger(__name__)


def create_qna_dto_from_ai_response(
    question_text: str,
    ai_raw_text: str,
    image_path: Optional[str] = None,
) -> QnACreateDTO:
    """AI의 원본 응답 텍스트를 파싱하여 QnACreateDTO 객체를 생성합니다"""

    # 제목 추출
    title_match = re.search(r"제목:\s*(.*)", ai_raw_text)
    title = title_match.group(1).strip() if title_match else "신규 질문"

    # 카테고리 추출
    category_match = re.search(r"카테고리:\s*(.*)", ai_raw_text)
    category = "General"
    if category_match:
        cat_text = category_match.group(1).strip()
        for cat in NOTION_CATEGORIES:
            if cat.lower() in cat_text.lower():
                category = cat
                break

    # 키워드 추출
    keywords_match = re.search(r"키워드:\s*(.*?)(?=\n|\[|$)", ai_raw_text, re.DOTALL)
    keywords = []
    if keywords_match:
        keywords = [k.strip() for k in keywords_match.group(1).split(",") if k.strip()]

    return QnACreateDTO(
        question_text=question_text,
        title=title,
        category=category,
        keywords=keywords,
        image_path=image_path,
        ai_answer=ai_raw_text,
        hit_count=1,
    )
def qna_model_to_create_dto(qna: QnALog) -> QnACreateDTO:
    """QnALog Django 모델 객체를 QnACreateDTO로 변환합니다"""
    return QnACreateDTO.model_validate(qna)

def qna_model_to_response_dto(qna: QnALog) -> QnAResponseDTO:
    """
    QnA Django 모델 객체를 QnAResponseDTO로 변환합니다
    pydantic의 from_attributes 기능 활용
    """
    return QnAResponseDTO.model_validate(qna)


class GeminiAdapter:
    """Gemini API와 통신을 전담하는 어댑터"""

    def __init__(self):
        self.api_key = getattr(settings, "GEMINI_API_KEY", None)
        if not self.api_key:
            raise LLMServiceError("GEMINI_API_KEY가 설정되지 않았습니다")
        self._client = genai.Client(api_key=self.api_key)

    def _build_prompt(self, question_text: str, context: str = "") -> str:
        context_section = ""
        if context:
            context_section = f"""
[참고 Q&A - 유사한 기존 질문과 답변]
{context}

위 참고 자료를 활용해서 답변해줘.
"""

        return f"""너는 불필요한 설명을 하지 않는 실력파 개발 조교야.
인사말은 생략하고 다음 구조로 핵심만 짧게 답해줘.

[메타데이터]
제목: (질문의 핵심 의도를 한문장으로)
카테고리: (다음중 하나 선택 - {",".join(NOTION_CATEGORIES)})
키워드: (핵심 키워드 3개를 쉼표로 구분)

[출력 양식]
1. **문제 요약**: (에러 정체 1문장)
2. **핵심 원인**: (이유 1~2개 불렛 포인트)
3. **해결 코드**: (중요 코드 블록. 설명은 주석으로)
4. **체크포인트**: (실수 방지 팁 하나)
{context_section}
질문 내용: {question_text}
"""

    def generate_answer(self, question_text: str, image_data: Optional[bytes] = None, context: str = "") -> QnACreateDTO:
        content_parts = []
        if image_data:
            try:
                img = Image.open(io.BytesIO(image_data))
                mime_type = f"image/{img.format.lower()}" if img.format else "image/jpeg"
                content_parts.append(types.Part.from_bytes(data=image_data, mime_type=mime_type))
                logger.info("이미지 로딩 성공")
            except Exception as e:
                logger.warning(f"이미지 로딩 에러: {e}")
        prompt = self._build_prompt(question_text, context)
        content_parts.append(prompt)

        try:
            response = self._client.models.generate_content(
                model="gemini-2.5-flash",
                contents=content_parts,
                config=types.GenerateContentConfig(
                    max_output_tokens=2048, temperature=0.7
                ),
            )

            if response.prompt_feedback and response.prompt_feedback.block_reason:
                block_reason = response.prompt_feedback.block_reason
                logger.warning(f"Gemini 응답 차단되었습니다. 이유: {block_reason}")
                raise LLMServiceError(f"AI 응답이 차단되었습니다: {block_reason}")

            if not response.text:
                finish_reason = response.candidates[0].finish_reason if response.candidates else 'N/A'
                logger.warning(f"Gemini 응답이 비어있음 이유: {finish_reason}")
                raise LLMServiceError("AI 응답이 비어있습니다")

            return create_qna_dto_from_ai_response(
                question_text=question_text,
                ai_raw_text =response.text
            )

        except LLMServiceError:
            raise
        except Exception as e:
            msg = str(e).lower()
            if "quota" in msg or "rate" in msg:
                logger.warning(f" Quota/Rate limit error {e}")
                raise LLMServiceError("API 할당량 초과, 나중에 재시도하세요")
            logger.error(f"Gemini API 에러 {e}", exc_info=True)
            raise LLMServiceError(f"AI 응답 생성 실패: {str(e)}")


class OpenAIEmbeddingAdapter:
    """OpenAI text-embedding-3-small 임베딩 어댑터"""

    def __init__(self):
        api_key = getattr(settings, "OPENAI_API_KEY", None)
        if not api_key:
            raise LLMServiceError("OPENAI_API_KEY가 설정되지 않았습니다")
        self.client = OpenAI(api_key=api_key)

    def embed(self, text: str) -> list[float]:
        response = self.client.embeddings.create(
            model="text-embedding-3-small",
            input=text,
        )
        return response.data[0].embedding


class NotionAdapter:
    """Notion API와 통신을 전담하는 어댑터"""

    def __init__(self):
        self.token = getattr(settings, "NOTION_TOKEN", None)
        self.database_id = getattr(settings, "NOTION_DB_ID", None)

        if not self.token or not self.database_id:
            raise NotionAPIError("NOTION_TOKEN 또는 NOTION_DB_ID가 설정되지 않았습니다")

        self.url = "https://api.notion.com/v1/pages"
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
            "Notion-Version": "2022-06-28",
        }

    def create_qna_page(self, dto: Union[QnACreateDTO, QnALog]) -> str:
        """DTO를 받아서 노션 페이지를 생성하고 생성된 페이지 URL 반환"""
        properties = {
            "이름": {"title": [{"text": {"content": (dto.title or "질문")[:100]}}]},
            "질문내용": {
                "rich_text": [
                    {"text": {"content": (dto.question_text or "내용 없음")[:1990]}}
                ]
            },
            "AI답변": {
                "rich_text": [
                    {"text": {"content": (dto.ai_answer or "답변 대기 중")[:1990]}}
                ]
            },
            "카테고리": {"select": {"name": dto.category or "General"}},
            "질문횟수": {"number": int(dto.hit_count or 1)},
        }

        # 멀티 셀렉트(키워드) 처리
        if dto.keywords:
            properties["키워드"] = {
                "multi_select": [{"name": kw[:50]} for kw in dto.keywords]
            }

        data = {"parent": {"database_id": self.database_id}, "properties": properties}

        try:
            # 타임아웃을 설정하여 무한 대기를 방지합니다
            response = requests.post(
                self.url, headers=self.headers, json=data, timeout=10
            )

            if response.status_code == 200:
                notion_url = response.json().get("url")
                logger.info(f"노션 페이지 생성 성공 {notion_url}")
                return notion_url
            else:
                error_detail = response.json()
                logger.error(f" 노션 API 에러 응답: {error_detail}")
                raise NotionAPIError(
                    f" 노션 API 에러 :{error_detail.get('message', 'unknown Error')}"
                )

        except requests.exceptions.RequestException as e:
            logger.error(f"노션 연결 중 네트워크 오류 발생 {e}")
            raise NotionAPIError(f" 노션 서버 연결 실패 {str(e)}")
