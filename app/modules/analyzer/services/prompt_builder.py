"""Build Anthropic system + user messages for Library matching."""

from dataclasses import dataclass

_MAX_RAW_LOG_CHARS = 500


@dataclass
class CatalogEntry:
    """One row of the LogType catalog sent to the LLM."""

    log_type_id: str
    vendor_slug: str
    product_slug: str
    log_type_name: str
    format: str
    sample: str | None


def build_match_system_prompt(catalog: list[CatalogEntry], top_k: int) -> str:
    """Build the (cacheable) system prompt embedding the catalog.

    Catalog changes invalidate the prompt cache, but vendor / product
    additions are infrequent so most calls hit the cache.
    """
    catalog_lines: list[str] = []
    for entry in catalog:
        sample_part = f' sample="{entry.sample[:120]}"' if entry.sample else ""
        catalog_lines.append(
            f"- id={entry.log_type_id} "
            f"vendor={entry.vendor_slug} product={entry.product_slug} "
            f"name={entry.log_type_name!r} format={entry.format}{sample_part}"
        )
    catalog_block = "\n".join(catalog_lines) if catalog_lines else "(empty)"

    return (
        "You are an expert at identifying log sources by their format. "
        "You will be given a raw log line and a catalog of known "
        "vendor/product/log-type combinations. Identify which (if any) "
        "candidates from the catalog best match the log line.\n"
        "\n"
        "Respond with ONLY valid JSON in this shape:\n"
        "{\n"
        '  "candidates": [\n'
        '    {"log_type_id": "<uuid from catalog>", '
        '"confidence": 0.0,  "reason": "<one short 繁體中文 sentence>"}\n'
        "  ]\n"
        "}\n"
        "\n"
        f"At most {top_k} entries, sorted by confidence descending. "
        "If no candidate matches, return an empty candidates array.\n"
        "\n"
        "Catalog:\n"
        f"{catalog_block}"
    )


def build_match_messages(raw_log: str) -> list[dict]:
    """Build the user-message list for `messages.create`."""
    truncated = raw_log[:_MAX_RAW_LOG_CHARS]
    return [
        {
            "role": "user",
            "content": f"Raw log:\n{truncated}\n\nIdentify the best candidates.",
        }
    ]
