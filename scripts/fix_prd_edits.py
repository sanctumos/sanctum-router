#!/usr/bin/env python3
"""One-off: fix PRD typos and malformed sentence (Unicode-safe)."""
import os
path = os.path.join(os.path.dirname(__file__), "..", "docs", "PRD_PROVIDER_MONITOR_ADAPTERS.md")
with open(path, "r", encoding="utf-8") as f:
    text = f.read()

# 1) Remove duplicate sentence: . quote stale quote the provider... (any quote chars)
import re
text = re.sub(
    r"(\. Do not mark the provider unhealthy solely due to credit fetch failure \(health is separate\)\.)\s*.\s*stale\s*.\s*the provider unhealthy solely due to credit fetch failure \(health is separate\)\.",
    r"\1",
    text,
)
# 2) Malformed response
text = text.replace(
    "return `CreditStatus(supported=True, balance=None, ...)` so the Router treats balance as unknown and does not enforce threshold (or treats as \u201cbelow threshold\u201d only if policy says \u201cunknown = exclude\u201d; Phase 1 recommendation: unknown = do not enforce).",
    "either return `CreditStatus(supported=True, balance=None, ...)` so the Router treats balance as unknown and does not enforce threshold, or raise and let the credit loop retain last-known-good (Phase 1 recommendation: unknown = do not enforce).",
)
# 3) Generic health: Router + any single char (apostrophe/quote) + Use
text = re.sub(r"\*\*Generic health:\*\*Router.Use the", "**Generic health:** Router: use the", text)

with open(path, "w", encoding="utf-8") as f:
    f.write(text)
print("PRD edits applied.")
