import pytest
from django.test import Client


def test_always_pass():
    assert True


def test_python_works():
    assert 1 + 1 == 2
    assert "hello".upper() == "HELLO"


@pytest.mark.django_db
def test_health_check_returns_200():
    client = Client()
    response = client.get("/health/")
    assert response.status_code == 200
    assert response.content == b"ok"
