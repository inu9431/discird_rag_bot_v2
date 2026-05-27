from django.urls import path

from . import views

app_name = "archiver"  # 템플릿에서 주소를 편하게 쓰기 위한 별칭

urlpatterns = [
    path(
        "qna/", views.QnABotAPIView.as_view(), name="qna_bot"
    ),  # http://127.0.0.1:8000/archiver/ 주소
]
