"""Discover pillar — mines Trends items for new voices worth following.

Three pieces, wired together by ``cli.py``:

* ``mining.py`` — counts how often unfollowed domains show up in Trends
  items; promotes a domain to a suggestion once it crosses a threshold.
* ``feed_discovery.py`` — best-effort RSS/Atom feed autodiscovery for a
  suggested domain.
* ``replies.py`` — polls Telegram for "approve <slug>" / "reject <slug>"
  replies and applies the decision to the store.
"""

from __future__ import annotations
