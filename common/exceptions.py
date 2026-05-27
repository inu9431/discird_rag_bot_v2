class BaseProjectError(Exception):
    """프로젝트 예외 클래스"""

    def __init__(self, message="오류가 발생했습니다"):
        self.message = message
        super().__init__(self.message)


class LLMServiceError(BaseProjectError): # 서비스 -> 에러 raise -> 메세지 -> 뷰에서 반환
    """Gemini API 등 AI 관련 오류"""

    pass


class NotionAPIError(BaseProjectError):
    """노션 API 전송 관련 오류"""

    pass


class SimilarityCheckError(BaseProjectError):
    """유사도 체크 과정에서의 오류"""

    pass
class ValidationError(BaseProjectError):
    """입력값 검증 실패시 발생"""
    pass

class AIResponseParsingError(BaseProjectError):
    """LLM의 응답을 파싱하는 과정에서 에러 발생시"""
    pass

class DatabaseOperationError(BaseProjectError):
    """데잍터베이스 작업 중 에러시 발생"""
    pass
