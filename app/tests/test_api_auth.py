"""认证 API 集成测试 — 使用 httpx.AsyncClient 测试 FastAPI 端点"""
import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from main import app


@pytest.fixture
async def client():
    """创建 ASGI 测试客户端，lifespan 事件由 async with 触发"""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac


@pytest.mark.asyncio
async def test_register_success(client):
    """POST /api/v1/auth/register 成功返回 code=0 及 access_token"""
    username = f"reg_{uuid.uuid4().hex[:12]}"
    resp = await client.post(
        "/api/v1/auth/register",
        json={"username": username, "password": "testpass123"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["code"] == 0
    assert "access_token" in data["data"]
    assert len(data["data"]["access_token"]) > 0


@pytest.mark.asyncio
async def test_register_duplicate(client):
    """重复注册同一用户名返回 400"""
    username = f"dup_{uuid.uuid4().hex[:12]}"
    # 第一次注册
    resp1 = await client.post(
        "/api/v1/auth/register",
        json={"username": username, "password": "testpass123"},
    )
    assert resp1.status_code == 200
    # 重复注册
    resp2 = await client.post(
        "/api/v1/auth/register",
        json={"username": username, "password": "testpass123"},
    )
    assert resp2.status_code == 400
    assert resp2.json()["code"] == 400


@pytest.mark.asyncio
async def test_login_success(client):
    """已注册用户登录成功返回 code=0"""
    username = f"login_{uuid.uuid4().hex[:12]}"
    password = "testpass123"
    # 先注册
    await client.post(
        "/api/v1/auth/register",
        json={"username": username, "password": password},
    )
    # 再登录
    resp = await client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": password},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["code"] == 0
    assert "access_token" in data["data"]


@pytest.mark.asyncio
async def test_login_wrong_password(client):
    """错误密码登录返回 401"""
    username = f"wrong_{uuid.uuid4().hex[:12]}"
    # 先注册
    await client.post(
        "/api/v1/auth/register",
        json={"username": username, "password": "correctpass"},
    )
    # 错误密码登录
    resp = await client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": "wrongpass"},
    )
    assert resp.status_code == 401
    assert resp.json()["code"] == 401


@pytest.mark.asyncio
async def test_get_me(client):
    """GET /api/v1/users/me 返回当前用户信息"""
    username = f"me_{uuid.uuid4().hex[:12]}"
    password = "testpass123"
    # 注册
    reg_resp = await client.post(
        "/api/v1/auth/register",
        json={"username": username, "password": password},
    )
    token = reg_resp.json()["data"]["access_token"]
    # 获取当前用户
    resp = await client.get(
        "/api/v1/users/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["code"] == 0
    assert data["data"]["username"] == username
