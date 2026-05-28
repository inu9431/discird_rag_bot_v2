import pytest
from django.test import Client


@pytest.mark.django_db
def test_health_check_returns_200():
    client = Client()
    response = client.get("/health/")
    assert response.status_code == 200
    assert response.content == b"ok"
