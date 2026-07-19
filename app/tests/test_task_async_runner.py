import asyncio

import pytest

from tasks.embed import _run_async_safe


@pytest.mark.skipif(
    not hasattr(asyncio, "WindowsSelectorEventLoopPolicy"),
    reason="Windows-only event loop policy check",
)
def test_run_async_safe_sets_windows_selector_policy(monkeypatch):
    calls = []
    original = asyncio.set_event_loop_policy

    def record_policy(policy):
        calls.append(policy)
        original(policy)

    async def noop():
        return "ok"

    monkeypatch.setattr(asyncio, "set_event_loop_policy", record_policy)

    assert _run_async_safe(noop()) == "ok"
    assert any(isinstance(policy, asyncio.WindowsSelectorEventLoopPolicy) for policy in calls)
