import json
import re


class NodeOutputError(Exception):
    pass


def extract_json(text: str) -> dict:
    stripped = text.strip()

    code_block_match = re.search(r"```(?:json)?\s*([\s\S]*?)```", stripped)
    if code_block_match:
        stripped = code_block_match.group(1).strip()

    start = stripped.find("{")
    if start == -1:
        raise NodeOutputError(f"No JSON object found in response: {stripped[:200]!r}")

    depth = 0
    end = None
    in_string = False
    escape = False
    for i in range(start, len(stripped)):
        ch = stripped[i]
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                end = i + 1
                break

    if end is None:
        raise NodeOutputError(f"Unbalanced JSON object in response: {stripped[:200]!r}")

    candidate = stripped[start:end]
    try:
        return json.loads(candidate)
    except json.JSONDecodeError as exc:
        raise NodeOutputError(f"Failed to parse JSON: {exc}") from exc
