import pytest


def test_always_pass():
    """기본 테스트 - 항상 통과"""
    assert True


def test_python_works():
    """Python 기본 동작 확인"""
    assert 1 + 1 == 2
    assert "hello".upper() == "HELLO"
