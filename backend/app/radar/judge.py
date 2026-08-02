"""LLM relevance+quality judgment for Radar's shortlisted candidates.
Pointwise scoring (one item judged per call, no cross-item comparison) —
the standard approach for this shape of ranking task, avoiding the
position-bias failure mode of pairwise/listwise judging. Quality is judged
from full article text with the source name given as context the model can
reason about, not a hardcoded per-source trust score (see spec's "Quality
vs. relevance" section for why). See
docs/superpowers/specs/2026-08-02-radar-content-discovery-design.md.
"""

import json
import re

from app.providers.base import Provider, ProviderConfigError, ProviderError, ProviderMissingError

MAX_ATTEMPTS = 2


class JudgeError(Exception):
    pass


def _strip_markdown_fence(raw: str) -> str:
    match = re.match(r"^\s*```(?:json)?\s*\n(.*)\n\s*```\s*$", raw, re.DOTALL)
    return match.group(1) if match else raw


def build_judge_prompt(article_text: str, source_name: str, interest_terms: list[str]) -> str:
    terms = ", ".join(interest_terms) if interest_terms else "(no specific interests recorded yet)"
    return f"""You are scoring one article as a candidate recommendation for a user's personal knowledge base.

Source: {source_name}
User's known interests: {terms}

Article text:
{article_text[:8000]}

Score this article on two independent dimensions, each 0.0 to 1.0:

1. relevance_score: how well this article matches the user's known interests above. 1.0 = directly on-topic, 0.0 = unrelated.

2. quality_score: how substantive this article is, considering:
   - depth and comprehensiveness of the treatment (not just length)
   - originality (new research/analysis/argument vs. rehashing something well-covered elsewhere)
   - evidence and rigor (backed by data/experiments/citations vs. pure opinion)
   - signal-to-noise (dense and information-rich vs. padded or clickbait-structured)
   - the source it's from, as context for what this publication typically produces (do not use source name alone as a shortcut — judge this article's actual content)
   1.0 = deep, original, rigorous. 0.0 = thin, derivative, or promotional.

Respond with JSON only, no markdown fence, no other text:
{{"relevance_score": <float>, "quality_score": <float>, "reasoning": "<one sentence explaining both scores>"}}
"""


def parse_judge_response(raw: str) -> dict:
    stripped = _strip_markdown_fence(raw)
    parsed = json.loads(stripped)

    for key in ("relevance_score", "quality_score", "reasoning"):
        if key not in parsed:
            raise ValueError(f"Judge response missing required key: {key}")

    for key in ("relevance_score", "quality_score"):
        value = parsed[key]
        if not isinstance(value, (int, float)) or not (0.0 <= value <= 1.0):
            raise ValueError(f"Judge response field {key} must be a number in [0.0, 1.0], got {value!r}")

    return {
        "relevance_score": float(parsed["relevance_score"]),
        "quality_score": float(parsed["quality_score"]),
        "reasoning": str(parsed["reasoning"]),
    }


def judge_item(provider: Provider, article_text: str, source_name: str, interest_terms: list[str]) -> dict:
    prompt = build_judge_prompt(article_text, source_name, interest_terms)

    last_error: Exception = ValueError("unknown error")
    for _ in range(MAX_ATTEMPTS):
        try:
            raw = provider.complete(prompt)
            return parse_judge_response(raw)
        except (ProviderMissingError, ProviderConfigError):
            raise
        except (ValueError, json.JSONDecodeError, ProviderError) as exc:
            last_error = exc
    raise JudgeError(f"Failed to get a valid judgment after {MAX_ATTEMPTS} attempts: {last_error}")
