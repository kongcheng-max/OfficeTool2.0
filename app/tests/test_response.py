"""响应模块测试"""
from core.response import APIResponse, PaginatedData


def test_success_response():
    """APIResponse.success() 返回 code=0"""
    resp = APIResponse.success(data="hello")
    assert resp.code == 0
    assert resp.message == "ok"
    assert resp.data == "hello"


def test_error_response():
    """APIResponse.error() 返回正确的 code/message"""
    resp = APIResponse.error(400, "bad")
    assert resp.code == 400
    assert resp.message == "bad"


def test_paginated_data():
    """PaginatedData 分页数据结构"""
    p = PaginatedData(items=[1, 2], total=2, page=1, page_size=10, total_pages=1)
    assert p.items == [1, 2]
    assert p.total == 2
    assert p.page == 1
    assert p.page_size == 10
    assert p.total_pages == 1
