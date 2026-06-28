"""安全模块测试 — JWT + bcrypt"""
import pytest
from core.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)


def test_hash_password():
    """hash_password 生成 bcrypt 哈希字符串"""
    hashed = hash_password("mysecret")
    assert isinstance(hashed, str)
    assert len(hashed) > 0
    assert hashed.startswith("$2")


def test_verify_password_correct():
    """正确密码匹配"""
    password = "mysecret"
    hashed = hash_password(password)
    assert verify_password(password, hashed) is True


def test_verify_password_incorrect():
    """错误密码不匹配"""
    hashed = hash_password("correct")
    assert verify_password("wrong", hashed) is False


def test_create_access_token():
    """create_access_token 返回非空 JWT 字符串"""
    token = create_access_token("user123")
    assert isinstance(token, str)
    assert len(token) > 0


def test_decode_access_token_valid():
    """有效 token 解码返回 user_id"""
    token = create_access_token("user123")
    user_id = decode_access_token(token)
    assert user_id == "user123"


def test_decode_access_token_invalid():
    """无效 token 解码返回 None"""
    result = decode_access_token("garbage.token.here")
    assert result is None
