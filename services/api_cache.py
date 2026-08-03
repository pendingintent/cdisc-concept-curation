"""Shared stale-tolerant in-memory cache for external API clients.

One caching strategy for all three clients (CDISC Library, NCI EVS,
NLM LOINC): serve fresh entries for CACHE_TTL seconds; on expiry attempt
a refresh but fall back to the stale entry (up to CACHE_STALE_TTL) rather
than propagating an error, so a slow or failing upstream never blanks a
page that rendered fine a minute ago.
"""

import logging
import time

logger = logging.getLogger(__name__)

# {key: (timestamp, data)} — entries are never evicted; stale data is the
# fallback when a refresh fails.
_cache = {}
CACHE_TTL = 300  # serve fresh data for 5 minutes
CACHE_STALE_TTL = 3600  # serve stale data for up to 1 hour while refresh fails


def cached(cache_key, fn):
    """Return cached data if fresh. If stale, attempt a refresh but fall back
    to the stale entry rather than propagating an error or blocking."""
    now = time.time()
    entry = _cache.get(cache_key)

    if entry and now - entry[0] < CACHE_TTL:
        return entry[1]  # fresh — serve immediately

    # Attempt a refresh. Broad catch is intentional: this is a resilience
    # seam and any refresh failure must fall back to stale data.
    try:
        data = fn()
        _cache[cache_key] = (now, data)
        return data
    except Exception:
        if entry and now - entry[0] < CACHE_STALE_TTL:
            logger.warning("Cache refresh failed for %s; serving stale entry", cache_key, exc_info=True)
            return entry[1]
        logger.error("Cache refresh failed for %s with no stale fallback", cache_key, exc_info=True)
        raise  # genuinely no data at all — let caller handle
