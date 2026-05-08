import re

_NON_ALNUM = re.compile(r"[^a-z0-9]+")


def slugify(text: str) -> str:
    """Convert text to a URL-safe slug.

    Lowercases, replaces non-alphanumeric runs with single hyphens,
    and strips leading/trailing hyphens. Does not handle Unicode normalization
    beyond ASCII fold; callers needing CJK support should pre-transliterate.
    """
    lowered = text.lower()
    hyphenated = _NON_ALNUM.sub("-", lowered)
    return hyphenated.strip("-")
