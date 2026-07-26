# Prompt template builders for content analysis tasks.
# Functions construct LLM prompts for triage, digest, critique, claims extraction,
# and cross-source comparison. Each function takes source metadata/content and returns
# a complete prompt string with explicit output format instructions (JSON).

from app.schemas.analysis import Claim


def build_triage_prompt(title: str, content: str) -> str:
    """Build a prompt for scoring content attention worthiness (0-100).

    Judges information density, originality, and clarity without penalizing
    brevity or informal style. Maps scores to reading priorities (must_read, skip, etc).
    """
    return f"""Score how much attention this content deserves, from 0-100. Judge information density (signal vs. noise), originality (genuine thinking vs. rehashed/generic content), and clarity (how well it's explained).

Do NOT penalize: brevity or concise format, informal style or personal-notes format, missing citations or data — judge the ideas themselves, not the packaging.

Map your score to an action: 80-100 -> must_read, 60-79 -> worth_reading, 40-59 -> skim, 20-39 -> summary_only, 0-19 -> skip. Also estimate read time in minutes.

Title: {title}

Content:
{content}

Return ONLY a JSON object: {{"score": <int 0-100>, "action": "<must_read|worth_reading|skim|summary_only|skip>", "reason": "<one sentence>", "read_time_minutes": <int>, "density": <int 0-100>, "originality": <int 0-100>}}"""


def build_digest_prompt(title: str, content: str) -> str:
    """Build a prompt for summarizing content and extracting key structure.

    Produces summary, highlights with source quotes, concepts (terms to define),
    and structure outline. Strictly adheres to what's in the content (no inference).
    Critical refinement: "text" may paraphrase for clarity, but "source_quote" must
    be an exact substring copied from the content.
    """
    return f"""Summarize this content and extract its key structure. Only include information explicitly stated in the text — do not infer, speculate, or add outside knowledge not present in the content.

- summary: 2-3 sentences capturing the main point.
- highlights: the most important individual statements (insight/fact/actionable). "text" may paraphrase the statement for clarity; "source_quote" must be an exact substring copied from the content below.
- concepts: jargon or key terms a reader might need defined (definitions may draw on general knowledge, unlike summary/highlights, since their purpose is explaining terms to the reader).
- structure: a short outline of the content's actual sections/flow.

Title: {title}

Content:
{content}

Return ONLY a JSON object: {{"summary": "<2-3 sentences>", "highlights": [{{"text": "<paraphrase>", "type": "<insight|fact|actionable>", "source_quote": "<exact substring>"}}], "concepts": [{{"term": "<term>", "definition": "<definition>"}}], "structure": ["<outline item>"]}}"""


def build_critique_prompt(title: str, content: str) -> str:
    """Build a prompt for critical evaluation across four categories.

    Evaluates hidden assumptions, potential issues, facts needing verification,
    and bias indicators. Each item requires a one-clause reason explaining why
    it qualifies. Empty lists are acceptable if genuinely nothing notable exists.
    """
    return f"""Critically evaluate this content across four categories. For each item you list, include a brief one-clause reason it qualifies — don't just assert it.

- hidden_assumptions: premises the author takes for granted without stating or justifying.
- potential_issues: logical gaps, overgeneralizations, or weak reasoning.
- needs_verification: specific factual claims a careful reader should check independently.
- bias_indicators: signs of one-sided framing, selective evidence, or unstated conflicts of interest.

If a category genuinely has nothing notable, return an empty list for it — do not invent items to fill it.

Title: {title}

Content:
{content}

Return ONLY a JSON object: {{"hidden_assumptions": ["<item with reason>"], "potential_issues": ["<item with reason>"], "needs_verification": ["<item with reason>"], "bias_indicators": ["<item with reason>"]}}"""


def build_claims_prompt(title: str, content: str) -> str:
    """Build a prompt for extracting up to 8 atomic, independently-checkable claims.

    Each claim is a self-contained statement (not compound) classified as factual
    (verifiable), opinion (author's judgment), or prediction (forecast). Each claim
    must reference an exact source quote from the content.
    """
    return f"""Extract up to 8 atomic, independently-checkable claims from this content. Each claim is one self-contained statement (not a compound sentence), classified as factual (verifiable against external reality), opinion (the author's judgment/interpretation), or prediction (a forecast about the future).

Each claim must include the exact quote from the text below it's grounded in.

Title: {title}

Content:
{content}

Return ONLY a JSON object: {{"claims": [{{"text": "<statement>", "type": "<factual|opinion|prediction>", "source_quote": "<exact substring>"}}]}}"""


def build_coarse_filter_prompt(new_title: str, new_summary: str, existing_summaries: list[dict]) -> str:
    """Build a prompt for identifying related existing sources by topic overlap.

    Given a new source's metadata and existing library sources (title+summary only),
    returns up to 5 existing source IDs that might have meaningful connection
    (topic overlap, potential contradiction, or conceptual extension). IDs ordered
    by relevance; empty list if none are meaningfully related.
    """
    existing_block = "\n".join(
        f"- ID: {s['id']}\n  Title: {s['title']}\n  Summary: {s['summary']}" for s in existing_summaries
    )
    return f"""Given a new source's title and summary, and a list of existing library sources (title + summary only), identify up to 5 existing sources that might have a meaningful connection to the new one — topic overlap, potential contradiction, or conceptual extension. Return their IDs only, ordered by relevance. If none are meaningfully related, return an empty list.

New Source
Title: {new_title}
Summary: {new_summary}

Existing Sources
{existing_block}

Return ONLY a JSON object: {{"candidate_ids": ["<id>", "..."]}}"""


def build_detailed_compare_prompt(new_source_id: str, new_claims: list[Claim], candidates: list[dict]) -> str:
    """Build a prompt for comparing claims across sources in detail.

    Takes a new source's claims and candidate sources' claims, classifies meaningful
    connections as contradicts/redundant/related. Only reports specific, meaningful
    connections—not superficial topic overlap. References claim IDs on both sides
    using format: new claim as-is, candidate claim as "sourceId:claimId".
    """
    new_claims_block = "\n".join(f"- [{c.id}] {c.text}" for c in new_claims)
    candidates_block = "\n\n".join(
        f"### {c['title']} (ID: {c['id']})\n" + "\n".join(f"- [{c['id']}:{claim.id}] {claim.text}" for claim in c["claims"])
        for c in candidates
    )
    return f"""Compare the new source's claims against the claims of each candidate source below. Classify each meaningful connection you find as:
- contradicts: a claim in the new source directly opposes a claim in a candidate.
- redundant: a claim in the new source restates a claim in a candidate with no new information.
- related: the sources share a concept or one extends the other, worth reading together.

Only report connections that are specific and meaningful — do not report superficial topic overlap. Reference the specific claim IDs on both sides (new source claim IDs as-is, candidate claim IDs as "sourceId:claimId").

New Source (ID: {new_source_id})
{new_claims_block}

Candidate Sources
{candidates_block}

Return ONLY a JSON object: {{"connections": [{{"type": "<contradicts|redundant|related>", "summary": "<one line>", "details": "<2-3 sentences>", "related_source_ids": ["<id>"], "claim_refs": ["<claimId or sourceId:claimId>"]}}]}}"""
