import logging
from .adapters import NotionAdapter, qna_model_to_create_dto
from .models import QnALog
logger = logging.getLogger(__name__)


def task_process_question(log_id):
    """
    worker 비동기 태스크
    QnALog id 를 받아 Notion 페이지를 생성하고 결과 url을 반환합니다
    """
    try:
        # DB에서 가져오기
        log = QnALog.objects.get(id=log_id)
        create_dto = qna_model_to_create_dto(log)


        # adapter 호출
        adapter = NotionAdapter()
        notion_url = adapter.create_qna_page(create_dto)

        # 결과 저장
        if notion_url:
            log.notion_page_url = notion_url
            log.save(update_fields=["notion_page_url"])
            logger.info(f"[worker] 노션 업로드 완료 (ID: {log.id})")
    except QnALog.DoesNotExist:
        logger.error(f"[worker] 해당 ID의 로그를 찾을 수 없음 (ID: {log_id})")
        #복구할수 없으므로 재시도하지 않도록 예외 처리
    except Exception as e:
        logger.error(f"[worker] 노션 업로드 실패 (ID: {log_id}): {str(e)}")
        # 실패시 예외를 다시 던져서 django-q가  실패로그를 남김
        raise e



