"""
Auto proxy finder — fetches a list of free non-RU proxies and returns the first working one.
Used at bot startup if PROXY_URL is not set in .env.
"""
import asyncio
import logging
import aiohttp

logger = logging.getLogger(__name__)

# ProxyScrape — plain text IP:PORT list, filtered by non-RU countries
PROXY_SOURCES = [
    # BY, DE, NL, PL, FI, EE, LV, LT, UA — fast filter
    "https://api.proxyscrape.com/v4/free-proxy-list/get?request=display_proxies&protocol=http&country=BY,DE,NL,UA,FI,EE,LV,LT,PL&anonymity=elite,anonymous&timeout=10000&format=text",
    # SOCKS5 non-RU
    "https://api.proxyscrape.com/v4/free-proxy-list/get?request=display_proxies&protocol=socks5&country=BY,DE,NL,UA,FI,EE,LV,LT,PL&timeout=10000&format=text",
    # Broader fallback — any country, elite/anon, longer timeout
    "https://api.proxyscrape.com/v4/free-proxy-list/get?request=display_proxies&protocol=http&anonymity=elite,anonymous&timeout=10000&format=text",
    # Raw GitHub list (updated frequently)
    "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt",
    "https://raw.githubusercontent.com/clarketm/proxy-list/master/proxy-list-raw.txt",
]

# Test against a plain HTTP URL first (no SSL) — faster, fewer failures
BASIC_TEST_URL = "http://www.google.com"
# Test against HTTPS Telegram API — this is CRITICAL for bot operation
TELEGRAM_TEST_URL = "https://api.telegram.org" 
CONNECT_TIMEOUT = aiohttp.ClientTimeout(connect=5, total=15)


async def _test_proxy(proxy_url: str) -> bool:
    """
    Check if the proxy can reach Telegram API via HTTPS.
    """
    try:
        async with aiohttp.ClientSession(timeout=CONNECT_TIMEOUT) as session:
            # We MUST use HTTPS here to verify the proxy supports tunneling
            async with session.get(TELEGRAM_TEST_URL, proxy=proxy_url, ssl=False) as resp:
                return resp.status < 500
    except Exception:
        return False


async def _fetch_proxies(source_url: str, session: aiohttp.ClientSession, is_socks5: bool = False) -> list[str]:
    """Download and parse a proxy list from a source URL."""
    proxies = []
    try:
        async with session.get(source_url) as resp:
            text = await resp.text()
            prefix = "socks5://" if is_socks5 else "http://"
            for line in text.splitlines():
                line = line.strip()
                # Skip comments and invalid lines
                if not line or line.startswith("#") or " " in line:
                    continue
                if ":" in line:
                    proxies.append(f"{prefix}{line}")
    except Exception as e:
        logger.debug(f"Failed to fetch {source_url}: {e}")
    return proxies


async def find_working_proxy(max_candidates: int = 60) -> str | None:
    """
    Fetch proxy lists from multiple sources, test them concurrently,
    and return the first working proxy URL, or None if nothing works.
    """
    candidates: list[str] = []

    fetch_timeout = aiohttp.ClientTimeout(total=15)
    async with aiohttp.ClientSession(timeout=fetch_timeout) as session:
        tasks = []
        for i, url in enumerate(PROXY_SOURCES):
            is_socks5 = "socks5" in url
            tasks.append(_fetch_proxies(url, session, is_socks5))
        results = await asyncio.gather(*tasks, return_exceptions=True)

    for result in results:
        if isinstance(result, list):
            candidates.extend(result)
        if len(candidates) >= max_candidates:
            break

    candidates = candidates[:max_candidates]

    if not candidates:
        logger.warning("No proxy candidates found from any source.")
        return None

    logger.info(f"Testing {len(candidates)} proxy candidates...")

    # Test in concurrent batches of 15
    batch_size = 15
    for i in range(0, len(candidates), batch_size):
        batch = candidates[i:i + batch_size]
        results = await asyncio.gather(*[_test_proxy(p) for p in batch])
        for proxy, ok in zip(batch, results):
            if ok:
                logger.info(f"✅ Working proxy found: {proxy}")
                return proxy
        logger.debug(f"Batch {i // batch_size + 1}: no working proxy yet, continuing...")

    logger.warning("⚠️ No working proxy found. Will connect directly to Telegram.")
    return None
