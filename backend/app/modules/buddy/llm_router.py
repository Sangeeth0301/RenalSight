"""Multi-provider LLM router with automatic fallback.

Every provider speaks the OpenAI-compatible chat API (Gemini, Groq, OpenAI, xAI Grok and Ollama all offer it),
so one small client covers them all, including tool calling. When a provider is out of quota, rate-limited,
timing out or has a bad key, the router pauses it (cooldown) and tries the next one. After the last provider the
caller falls back to rule-based answers (no AI), so the app never breaks.
"""
from __future__ import annotations

import time
from dataclasses import dataclass

import httpx

from ...core.config import get_settings

PROVIDER_DEFS = {
    "gemini": ("https://generativelanguage.googleapis.com/v1beta/openai", "gemini_api_key", "gemini_model"),
    "groq": ("https://api.groq.com/openai/v1", "groq_api_key", "groq_model"),
    "openai": ("https://api.openai.com/v1", "openai_api_key", "openai_model"),
    "xai": ("https://api.x.ai/v1", "xai_api_key", "xai_model"),
    "ollama": (None, None, "ollama_model"),
}
# providers that handle Tamil / Bengali / Telugu best are tried first for those languages
STRONG_MULTILINGUAL = ("gemini", "openai")


class ProviderError(Exception):
    def __init__(self, status: int | None, message: str):
        super().__init__(message)
        self.status, self.message = status, message


class AllProvidersFailed(Exception):
    def __init__(self, errors: dict):
        super().__init__("all providers failed")
        self.errors = errors


@dataclass
class ProviderState:
    name: str
    successes: int = 0
    failures: int = 0
    consecutive: int = 0
    cooldown_until: float = 0.0
    last_error: str | None = None
    last_used: float | None = None


def call_provider(cfg: dict, payload: dict, timeout: float) -> dict:
    """One HTTP call to an OpenAI-compatible endpoint. Replaced by a fake in tests."""
    headers = {"Content-Type": "application/json"}
    if cfg.get("api_key"):
        headers["Authorization"] = f"Bearer {cfg['api_key']}"
    try:
        r = httpx.post(cfg["base_url"].rstrip("/") + "/chat/completions", json={**payload, "model": cfg["model"]}, headers=headers, timeout=timeout)
    except (httpx.TimeoutException, httpx.TransportError) as e:
        raise ProviderError(None, f"network: {type(e).__name__}")
    if r.status_code != 200:
        raise ProviderError(r.status_code, r.text[:300])
    return r.json()


class LLMRouter:
    def __init__(self, chain: list[str] | None = None, cfgs: dict | None = None, timeout: float | None = None, clock=time.monotonic):
        s = get_settings()
        self.chain = [c.strip() for c in (chain if chain is not None else s.llm_chain.split(",")) if c.strip()]
        self.timeout = timeout or s.llm_timeout_seconds
        self.clock = clock
        self.cfgs = cfgs if cfgs is not None else self._cfgs_from_settings(s)
        self.state = {n: ProviderState(n) for n in self.chain if n != "rules"}

    @staticmethod
    def _cfgs_from_settings(s) -> dict:
        out = {}
        for name, (base, key_attr, model_attr) in PROVIDER_DEFS.items():
            if name == "ollama":
                out[name] = {"base_url": s.ollama_base_url, "api_key": "", "model": s.ollama_model, "enabled": s.ollama_enabled}
            else:
                key = getattr(s, key_attr)
                out[name] = {"base_url": base, "api_key": key, "model": getattr(s, model_attr), "enabled": bool(key)}
        return out

    # ------------------------------------------------------------ chain handling
    def ordered(self, language: str = "en") -> list[str]:
        names = [n for n in self.chain if n != "rules" and self.cfgs.get(n, {}).get("enabled")]
        if language != "en":
            names.sort(key=lambda n: 0 if n in STRONG_MULTILINGUAL else 1)     # stable sort keeps the configured order otherwise
        return names

    def available(self, language: str = "en") -> list[str]:
        now = self.clock()
        return [n for n in self.ordered(language) if self.state[n].cooldown_until <= now]

    def _penalise(self, st: ProviderState, err: ProviderError):
        st.failures += 1
        st.consecutive += 1
        st.last_error = f"{err.status or 'error'}: {err.message[:120]}"
        if err.status in (401, 403):
            cool = 3600                                       # bad / expired key: do not hammer it
        elif err.status == 429:
            cool = min(60 * 2 ** (st.consecutive - 1), 900)   # quota or rate limit: back off 1, 2, 4... up to 15 minutes
        elif err.status is None or err.status >= 500:
            cool = min(20 * st.consecutive, 300)
        else:
            cool = 0                                          # 400-type: this request was the problem, just try the next provider
        st.cooldown_until = self.clock() + cool

    # ------------------------------------------------------------ main call
    def chat(self, messages: list[dict], tools: list[dict] | None = None, language: str = "en", max_tokens: int = 700) -> tuple[str, dict]:
        errors: dict[str, str] = {}
        payload = {"messages": messages, "temperature": 0.3, "max_tokens": max_tokens}
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"
        for name in self.available(language):
            st = self.state[name]
            try:
                data = call_provider({**self.cfgs[name], "name": name}, payload, self.timeout)
                msg = data["choices"][0]["message"]
            except ProviderError as e:
                self._penalise(st, e)
                errors[name] = st.last_error
                continue
            except (KeyError, IndexError, TypeError, ValueError):
                self._penalise(st, ProviderError(502, "malformed response"))
                errors[name] = st.last_error
                continue
            st.successes += 1
            st.consecutive = 0
            st.last_used = self.clock()
            return name, msg
        raise AllProvidersFailed(errors)

    def status(self) -> list[dict]:
        now = self.clock()
        rows = []
        for name in self.chain:
            if name == "rules":
                rows.append({"provider": "rules", "state": "always_available", "configured": True, "note": "rule-based answers, no AI"})
                continue
            st, cfg = self.state[name], self.cfgs.get(name, {})
            state = "not_configured" if not cfg.get("enabled") else "cooldown" if st.cooldown_until > now else "ready"
            rows.append({"provider": name, "state": state, "configured": bool(cfg.get("enabled")), "model": cfg.get("model"),
                         "successes": st.successes, "failures": st.failures, "last_error": st.last_error,
                         "cooldown_seconds_left": max(0, round(st.cooldown_until - now))})
        return rows

    def any_ready(self, language: str = "en") -> bool:
        return bool(self.available(language))


_router: LLMRouter | None = None


def get_router() -> LLMRouter:
    global _router
    if _router is None:
        _router = LLMRouter()
    return _router


def set_router(r: LLMRouter | None):
    global _router
    _router = r
