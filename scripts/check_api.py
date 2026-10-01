"""Phase 0 check: confirm the API key works with the configured model."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import anthropic

from core.config import MODEL, cost_usd

client = anthropic.Anthropic()
try:
    r = client.messages.create(
        model=MODEL,
        max_tokens=64,
        output_config={"effort": "low"},
        messages=[{"role": "user", "content": "Reply with exactly: OK"}],
    )
except anthropic.AuthenticationError:
    sys.exit("FAIL: API key rejected (check .env)")
except anthropic.NotFoundError:
    sys.exit(f"FAIL: model {MODEL} not found for this key")
except anthropic.APIConnectionError:
    sys.exit("FAIL: could not reach api.anthropic.com (network/proxy?)")

text = next((b.text for b in r.content if b.type == "text"), "")
print(f"model={r.model} reply={text!r} stop={r.stop_reason}")
print(f"tokens in={r.usage.input_tokens} out={r.usage.output_tokens} "
      f"cost=${cost_usd(MODEL, r.usage.input_tokens, r.usage.output_tokens):.5f}")
