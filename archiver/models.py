from django.db import models
from django_q.tasks import async_task
from pgvector.django import VectorField, IvfflatIndex


class QnALog(models.Model):
    category = models.CharField(
        max_length=50,
        default="General",
        verbose_name="카테고리",
    )

    title = models.CharField(max_length=200)  # AI가 요약한 제목
    question_text = models.TextField()  # 학생 질문
    image = models.ImageField(upload_to="qna_images/", null=True, blank=True)
    ai_answer = models.TextField()  # AI가 정리한 답변

    is_verified = models.BooleanField(default=False, verbose_name="검증 완료")
    hit_count = models.PositiveIntegerField(default=0, verbose_name="질문 빈도")
    parent_question = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sub_questions",
        verbose_name="상위 질문",
    )

    embedding = VectorField(dimensions=1536, null=True, blank=True)

    notion_page_url = models.URLField(
        max_length=500, null=True, blank=True, verbose_name="노션 페이지 링크"
    )
    keywords = models.TextField(
         blank=True, null=True, verbose_name="세부 키워드"
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="생성일")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="수정일")

    class Meta:
        verbose_name = "Q&A Log"
        verbose_name_plural = "Q&A 로그 목록"
        ordering = ["-created_at"]

        indexes = [
            IvfflatIndex(
                fields=["embedding"],
                name="qna_embedding_ivfflat_idx",
                lists=100,
            ),
        ]

    def __str__(self):
        return f"[{self.category}] {self.title} (빈도: {self.hit_count})"

    # 검증되고 노션 url이 없는 경우에만 워커 호출
    def save(self, *args, **kwargs):
        if self.is_verified and not self.notion_page_url:
            super().save(*args, **kwargs)
            async_task("archiver.tasks.task_process_question", self.id)
        else:
            super().save(*args, **kwargs)

