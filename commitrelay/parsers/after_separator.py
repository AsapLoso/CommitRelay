"""Publish only content after the first standalone Markdown --- line."""

def parse(content: str, options=None) -> str | None:
    lines = content.splitlines(keepends=True)
    for i, line in enumerate(lines):
        if line.strip() == "---":
            body = "".join(lines[i + 1:]).strip()
            return body or None
    return None  # Fail closed; never reveal comments if divider is missing.
