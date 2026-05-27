from pydantic import BaseModel, Field, ConfigDict, field_validator
from typing import List, Optional, Any
from datetime import datetime




class QnACreateDTO(BaseModel):
    """AI 분석 결과를 바탕으로 QnA 생성을 요청할떄 사용하는 데이터 전송 객체"""
    model_config = ConfigDict(frozen = True,from_attributes=True)

    question_text: str
    title: str
    reason: Optional[str] = None
    solution_code: Optional[str] = None
    checkpoint: Optional[str] = None
    category: Optional[str] = "General"
    keywords: List[str] = Field(default_factory=list)
    image_path: Optional[str] = None
    ai_answer: Optional[str] = None
    hit_count: Optional[int] = 1

    @field_validator("keywords", mode='before')
    @classmethod
    def split_keywords(cls, v: Any) -> List[str]:
        if isinstance(v, str):
            return [item.strip() for item in v.split(',') if item.strip()]
        if v is None:
            return []
        return v


class QnAResponseDTO(BaseModel):
        model_config = ConfigDict(frozen = True,from_attributes=True)

        id: int
        question_text: str
        title: str
        reason: Optional[str] = None
        solution_code: Optional[str] = None
        checkpoint: Optional[str] = None
        category: Optional[str] = None
        keywords: Optional[List[str]] = None
        image_path: Optional[str] = None
        ai_answer: Optional[str] = None
        hit_count: Optional[int] = 1
        created_at: Optional[datetime] = None

        @field_validator("keywords", mode='before')
        @classmethod
        def split_keywords(cls, v: Any) -> List[str]:
            if isinstance(v, str):
                return [item.strip() for item in v.split(',') if item.strip()]
            if v is None:
                return []
            return v
