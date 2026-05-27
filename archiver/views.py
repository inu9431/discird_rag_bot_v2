import logging

from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from drf_spectacular.utils import extend_schema, inline_serializer, OpenApiExample
from rest_framework import serializers
from rest_framework.response import Response
from rest_framework.views import APIView
from common.exceptions import ValidationError, LLMServiceError, AIResponseParsingError, DatabaseOperationError
from .services import QnAService
from .adapters import qna_model_to_response_dto

logger = logging.getLogger(__name__)


@method_decorator(csrf_exempt, name="dispatch")
class QnABotAPIView(APIView):
    @extend_schema(
        summary="질문 처리 및 유사 질문 검색",
        description=(
            "질문 텍스트와 선택적 이미지를 받아 유사한 기존 질문이 있으면 반환하고, "
            "없으면 AI가 분석한 새 QnA를 생성합니다."
        ),
        request=inline_serializer(
            name="QnARequest",
            fields={
                "question_text": serializers.CharField(help_text="질문 내용"),
                "image": serializers.ImageField(required=False, help_text="첨부 이미지 (선택)"),
            },
        ),
        responses={
            200: {
                "type": "object",
                "properties": {
                    "id": {"type": "integer"},
                    "question_text": {"type": "string"},
                    "title": {"type": "string"},
                    "reason": {"type": "string", "nullable": True},
                    "solution_code": {"type": "string", "nullable": True},
                    "checkpoint": {"type": "string", "nullable": True},
                    "category": {"type": "string", "nullable": True},
                    "keywords": {"type": "array", "items": {"type": "string"}},
                    "image_path": {"type": "string", "nullable": True},
                    "ai_answer": {"type": "string", "nullable": True},
                    "hit_count": {"type": "integer"},
                    "created_at": {"type": "string", "format": "date-time"},
                    "status": {"type": "string", "enum": ["similar_found", "new"]},
                    "message": {"type": "string"},
                },
            },
            400: {"description": "잘못된 요청"},
            503: {"description": "AI 서비스 오류"},
        },
        examples=[
            OpenApiExample(
                "새 질문 처리 응답",
                value={
                    "id": 1,
                    "question_text": "파이썬에서 리스트 컴프리헨션은 어떻게 쓰나요?",
                    "title": "파이썬 리스트 컴프리헨션 사용법",
                    "ai_answer": "[x for x in range(10) if x % 2 == 0]",
                    "status": "new",
                    "message": "AI 분석이 끝났습니다",
                },
                response_only=True,
            ),
        ],
    )
    def post(self, request):
        try:
            logger.info("QnABotAPIView POST called")
            question_text = request.data.get("question_text")
            image = request.FILES.get("image")

            service = QnAService()

            # 유사도 체크
            similarity_result = service.check_similarity(question_text)


            if similarity_result['status'] == 'similar_found':
                return Response(similarity_result['data'])

            # 새로운 질문 처리
            new_log = service.process_question_flow(
                question_text=question_text,
                image=image
            )

            response_dto = qna_model_to_response_dto(new_log)
            response_data = response_dto.model_dump()
            response_data["status"] = "new"
            response_data["message"] = "AI 분석이 끝났습니다"

            return Response(response_data)

        except ValidationError as e:
            # 클라이언트 요청이 잘못된 경우
            return Response({"error": e.message}, status=400)
        except LLMServiceError as e:
            # 외부 서비스에 문제가 생긴경우
            return Response({"error": e.message}, status=503)
        except AIResponseParsingError as e:
            return Response({"error": e.message}, status=400)
        except DatabaseOperationError as e:
            # 파싱 문제인 경우
            return Response({"error": e.message}, status=500)
        except Exception as e:
            logger.error(f"알수없는 에러 발생 {e}", exc_info=True)
            return Response({"error": "알수없는 에러 발생"}, status=500)