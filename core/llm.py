"""Shared Claude client, structured-output call helper, and request logging."""
import json
import time
from datetime import datetime, timezone

import anthropic

from core.config import LOG_DIR, MODEL

_client: anthropic.Anthropic | None = None


def client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        # Calls normally finish in 5-15 s; the SDK default (10 min) makes a hung connection look like a freeze.
        # On timeout the SDK retries (max_retries=2) before raising APITimeoutError.
        _client = anthropic.Anthropic(timeout=90.0, max_retries=2)
    return _client


class ClaudeCallError(RuntimeError):
    pass


def parse_call(call_type: str, output_format, messages, system: str, effort: str,
               max_tokens: int = 8000, meta: dict | None = None):
    """Run one structured-output request. Returns (parsed_output, usage dict). Logs every call."""
    started = time.time()
    resp = client().messages.parse(
        model=MODEL,
        max_tokens=max_tokens,
        system=system,
        thinking={"type": "adaptive"},
        output_config={"effort": effort},
        output_format=output_format,
        messages=messages,
    )
    usage = {"input_tokens": resp.usage.input_tokens, "output_tokens": resp.usage.output_tokens}
    _log({
        "ts": datetime.now(timezone.utc).isoformat(),
        "call": call_type,
        "model": resp.model,
        "request_id": resp._request_id,
        "stop_reason": resp.stop_reason,
        "seconds": round(time.time() - started, 2),
        "usage": usage,
        "meta": meta or {},
        "output": resp.parsed_output.model_dump() if resp.parsed_output else None,
    })
    if resp.stop_reason == "refusal":
        raise ClaudeCallError(f"{call_type}: model declined the request")
    if resp.stop_reason == "max_tokens" or resp.parsed_output is None:
        raise ClaudeCallError(f"{call_type}: incomplete output (stop_reason={resp.stop_reason})")
    return resp.parsed_output, usage


def text_call(call_type: str, messages, system: str, effort: str,
              max_tokens: int = 8000, meta: dict | None = None) -> tuple[str, dict]:
    """Run one plain-text request. Returns (text, usage dict). Logs every call."""
    started = time.time()
    resp = client().messages.create(
        model=MODEL,
        max_tokens=max_tokens,
        system=system,
        thinking={"type": "adaptive"},
        output_config={"effort": effort},
        messages=messages,
    )
    usage = {"input_tokens": resp.usage.input_tokens, "output_tokens": resp.usage.output_tokens}
    text = "".join(b.text for b in resp.content if b.type == "text").strip()
    _log({
        "ts": datetime.now(timezone.utc).isoformat(),
        "call": call_type,
        "model": resp.model,
        "request_id": resp._request_id,
        "stop_reason": resp.stop_reason,
        "seconds": round(time.time() - started, 2),
        "usage": usage,
        "meta": meta or {},
        "output": text,
    })
    if resp.stop_reason == "refusal":
        raise ClaudeCallError(f"{call_type}: model declined the request")
    if resp.stop_reason == "max_tokens" or not text:
        raise ClaudeCallError(f"{call_type}: incomplete output (stop_reason={resp.stop_reason})")
    return text, usage


def _log(record: dict) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    path = LOG_DIR / f"{datetime.now():%Y-%m-%d}.jsonl"
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
