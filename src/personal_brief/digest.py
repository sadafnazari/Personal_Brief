"""Render and persist the daily digest.

Two renderings of the same grouped structure: ``render_digest`` produces a
local HTML file (every run writes one, regardless of delivery config) and
``render_telegram_messages`` produces a list of Telegram-HTML messages, one
per section, so the digest reads as distinct cards instead of one blob.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from html import escape
from pathlib import Path

from personal_brief.models import Item, Pillar

DIGESTS_SUBDIR = "digests"

_SECTION_HEADINGS: dict[Pillar, str] = {
    Pillar.FOLLOW: "Following",
    Pillar.TRENDS: "Trending",
    Pillar.DISCOVER: "Discover",
}

_SECTION_EMOJI: dict[Pillar, str] = {
    Pillar.FOLLOW: "📰",
    Pillar.TRENDS: "🔥",
    Pillar.DISCOVER: "🔍",
}


def render_digest(items: Sequence[Item], summary: str, generated_at: datetime) -> str:
    """Render items and their summary as a small, self-contained HTML page.

    Items are grouped into sections by pillar (Following, Trending, Discover),
    in that order, so the digest reads as three distinct concerns rather than
    one undifferentiated list.
    """
    sections_html = (
        "\n".join(
            _render_section(_SECTION_HEADINGS[pillar], group)
            for pillar in _SECTION_HEADINGS
            if (group := [item for item in items if item.pillar is pillar])
        )
        or "<p>Nothing new today.</p>"
    )
    summary_html = escape(summary).replace("\n", "<br>")
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Personal Brief — {generated_at:%Y-%m-%d}</title>
<style>
  body {{ font-family: system-ui, sans-serif; max-width: 42rem; margin: 2rem auto; \
padding: 0 1rem; line-height: 1.5; color: #1a1a1a; }}
  h1 {{ font-size: 1.4rem; }}
  h2 {{ font-size: 1.1rem; margin-top: 2rem; }}
  .summary {{ background: #f6f6f4; border-radius: 0.5rem; padding: 1rem 1.25rem; }}
  .item {{ margin: 0.75rem 0; }}
  .item .source {{ color: #666; font-size: 0.9rem; }}
  a {{ color: #0b5fff; text-decoration: none; }}
  a:hover {{ text-decoration: underline; }}
</style>
</head>
<body>
  <h1>Personal Brief — {generated_at:%A, %B %d %Y}</h1>
  <div class="summary">{summary_html}</div>
  {sections_html}
</body>
</html>
"""


def _render_section(heading: str, items: Sequence[Item]) -> str:
    items_html = "\n".join(_render_item(item) for item in items)
    return f"<h2>{escape(heading)} ({len(items)})</h2>\n{items_html}"


def _render_item(item: Item) -> str:
    author = escape(item.author or item.source)
    title = escape(item.title)
    url = escape(item.url)
    score_html = f" · {item.score} pts" if item.score is not None else ""
    return (
        f'<div class="item"><a href="{url}">{title}</a>'
        f'<div class="source">{author} · {escape(item.source)}{score_html}</div></div>'
    )


def render_telegram_messages(
    items: Sequence[Item], summary: str, generated_at: datetime
) -> list[str]:
    """Render the digest as a list of Telegram-HTML messages, one per section.

    A header message (bold title + summary) comes first, then one message
    per non-empty pillar — bold heading, an emoji, and each item's title as
    a tappable link — instead of one long blob. Every piece of user-derived
    text is HTML-escaped before being placed inside a tag, the same
    ``html.escape`` pattern ``render_digest`` already uses, since Telegram's
    HTML ``parse_mode`` only tolerates a narrow, well-formed tag subset.
    """
    messages = [f"<b>Personal Brief — {generated_at:%A, %B %d %Y}</b>\n\n{escape(summary)}"]

    for pillar, heading in _SECTION_HEADINGS.items():
        group = [item for item in items if item.pillar is pillar]
        if not group:
            continue
        emoji = _SECTION_EMOJI[pillar]
        item_blocks = (_render_telegram_item(item) for item in group)
        messages.append(f"{emoji} <b>{heading} ({len(group)})</b>\n\n" + "\n\n".join(item_blocks))

    return messages


def _render_telegram_item(item: Item) -> str:
    author = escape(item.author or item.source)
    title = escape(item.title)
    url = escape(item.url)
    score = f" · {item.score} pts" if item.score is not None else ""
    return f'• <a href="{url}">{title}</a>\n  {author}{score}'


def write_digest(html: str, data_dir: Path, generated_at: datetime) -> Path:
    """Write the rendered digest to ``data_dir/digests/YYYY-MM-DD.html`` and return the path."""
    digests_dir = data_dir / DIGESTS_SUBDIR
    digests_dir.mkdir(parents=True, exist_ok=True)
    path = digests_dir / f"{generated_at:%Y-%m-%d}.html"
    path.write_text(html, encoding="utf-8")
    return path
