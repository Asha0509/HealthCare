"""Shared test setup: isolated databases, no real LLM keys, fake LLM transport."""
import json
import os
import sys
import tempfile

import pytest

_TMP = tempfile.mkdtemp(prefix="healthai-tests-")
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{_TMP}/app.db"
os.environ["OBS_DB_PATH"] = f"{_TMP}/obs.db"
os.environ["GROQ_API_KEY"] = ""
os.environ["NVIDIA_NIM_API_KEY"] = ""
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.config import settings  # noqa: E402
from services import llm_client, observability  # noqa: E402


@pytest.fixture(autouse=True)
def isolated_obs(tmp_path):
    observability.reset_for_tests(str(tmp_path / "obs.db"))
    yield


@pytest.fixture
def no_llm(monkeypatch):
    monkeypatch.setattr(settings, "GROQ_API_KEY", "")
    monkeypatch.setattr(settings, "NVIDIA_NIM_API_KEY", "")


def tool_call(name, args, call_id=None):
    return {"id": call_id or f"call_{name}", "type": "function",
            "function": {"name": name, "arguments": json.dumps(args)}}


def reply(content="", tool_calls=None, prompt_tokens=100, completion_tokens=20):
    msg = {"role": "assistant", "content": content}
    if tool_calls:
        msg["tool_calls"] = tool_calls
    return {"choices": [{"message": msg}],
            "usage": {"prompt_tokens": prompt_tokens, "completion_tokens": completion_tokens}}


class ScriptedLLM:
    """Fake provider transport that returns scripted replies in order and records requests."""

    def __init__(self, replies, fail_providers=()):
        self.replies = list(replies)
        self.fail_providers = set(fail_providers)
        self.requests = []

    def __call__(self, provider, payload):
        self.requests.append((provider.name, payload))
        if provider.name in self.fail_providers:
            raise RuntimeError(f"{provider.name} down")
        if not self.replies:
            raise RuntimeError("script exhausted")
        return self.replies.pop(0)


@pytest.fixture
def fake_llm(monkeypatch):
    """Configure both providers with dummy keys and install a scripted transport."""
    monkeypatch.setattr(settings, "GROQ_API_KEY", "test-groq")
    monkeypatch.setattr(settings, "NVIDIA_NIM_API_KEY", "test-nim")

    def install(replies, fail_providers=()):
        script = ScriptedLLM(replies, fail_providers)
        monkeypatch.setattr(llm_client, "transport", script)
        return script
    return install
