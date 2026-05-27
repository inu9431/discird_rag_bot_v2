import logging
from typing import Optional

from django.core.files.uploadedfile import UploadedFile
from pgvector.django import CosineDistance

from .adapters import GeminiAdapter, NotionAdapter, OpenAIEmbeddingAdapter, qna_model_to_response_dto
from .models import QnALog
from common.exceptions import AIResponseParsingError, DatabaseOperationError, ValidationError

logger = logging.getLogger(__name__)


class QnAService:

    def __init__(self):
        self.gemini = GeminiAdapter()
        self.notion = NotionAdapter()
        self.embedding = OpenAIEmbeddingAdapter()

    def check_similarity(self, question_text: str, threshold=0.2):
        """pgvector 코사인 거리로 유사 질문 검색 (distance < threshold = 유사)"""
        logger.debug("============== pgvector 유사도 체크 시작 ==============")

        query_embedding = self.embedding.embed(question_text)

        similar_log = (
            QnALog.objects.filter(embedding__isnull=False, is_verified=True)
            .annotate(distance=CosineDistance("embedding", query_embedding))
            .filter(distance__lt=threshold)
            .order_by("distance")
            .first()
        )


        if not similar_log:
            return {
                'status': 'not_found',
                'data': None
            }

        similar_log.hit_count += 1
        similar_log.save(update_fields=["hit_count"])
        logger.info(f" 유사 질문 발견 (검토 대기중): {similar_log.id}")

        # DTO 변환
        response_dto = qna_model_to_response_dto(similar_log)
        response_data = response_dto.model_dump()

        # status 추가
        response_data["status"] = "similar_found"

        return {
           'status': 'similar_found',
            'data': response_data
        }

    def retrieve_context(self, question_text: str, top_k: int = 3) -> str:
        """유사 Q&A top-k를 검색해 RAG 컨텍스트 문자열로 반환"""
        query_embedding = self.embedding.embed(question_text)

        related = (
            QnALog.objects.filter(embedding__isnull=False, is_verified=True)
            .annotate(distance=CosineDistance("embedding", query_embedding))
            .filter(distance__lt=0.5)
            .order_by("distance")[:top_k]
        )

        if not related:
            return ""

        return "\n\n".join(
            f"Q: {log.question_text}\nA: {log.ai_answer}" for log in related
        )

    def process_question_flow(self, question_text: str, image: Optional[UploadedFile] = None) -> QnALog:
        """
        이미 생성된 log_obj를 받아서 AI 분석 결과로 업데이트
        """
        try:
            if not question_text:
                raise ValidationError("질문을 입력해주세요")

            image_data = None
            if image:
                image_data = image.read()

            context = self.retrieve_context(question_text)
            dto = self.gemini.generate_answer(question_text, image_data, context=context)



            log_obj = QnALog.objects.create(
                question_text=question_text,
                title=dto.title,
                ai_answer=dto.ai_answer,
                category=dto.category,
                keywords=dto.keywords,
                image=image,
            )

            try:
                log_obj.embedding = self.embedding.embed(question_text)
                log_obj.save(update_fields=["embedding"])
            except Exception as e:
                logger.warning(f"임베딩 저장 실패 ID:{log_obj.id}: {e}")

            try:
                notion_page_url = self.notion.create_qna_page(log_obj)
                log_obj.notion_page_url = notion_page_url
                log_obj.save(update_fields=["notion_page_url"])
                logger.info(f"Notion 아카이빙 성공: {log_obj.id}, URL: {notion_page_url}")
            except Exception as e:
                logger.error(f"Notion 저장 실패 ID: {log_obj.id}: {e}", exc_info=True)

            return log_obj

        except (AttributeError, TypeError, IndexError) as e:
            logger.error(f"신규 질문 처리중 에러 발생 {e}")
            if 'log_obj' in locals():
                log_obj.title = "AI 응답 파싱 실패"
                log_obj.save()
            raise AIResponseParsingError("AI 응답 형식(키워드, 제목)이 형식에 맞지않습니다")
        except AIResponseParsingError:
            raise
        except ValidationError:
            raise
        except Exception as e:
            logger.error(f"데이터베이스 저장 중 오류 발생: {e}", exc_info=True)
            raise DatabaseOperationError("결과를 데이터베이스에 저장하는 중 문제가 발생했습니다")


