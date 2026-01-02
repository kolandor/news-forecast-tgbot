
import asyncio
import json
import logging
import time
from dataclasses import dataclass
from typing import Dict, Any, Optional, Tuple, List

from playwright.async_api import async_playwright, Page
from config import API_BASE_URL, REQUEST_TIMEOUT_SEC

logger = logging.getLogger(__name__)

# Heuristics for "final" JSON in <pre>
MIN_SUMMARY_LEN = 20  # Adapted to 20 as per recent context, or stick to provided 50? User script said 50. Let's start with 20 to be safe or 50 if user insists. User provided script says 50.
MIN_SOURCES_LEN = 1

@dataclass
class Inspection:
    final_data: Optional[Dict[str, Any]] = None
    loading_present: bool = False
    api_key_invalid: bool = False

def is_final_report(data: Any) -> Tuple[bool, str]:
    """
    Returns (ok, reason). We accept only a "final-looking" report:
      - dict with results: list[dict]
      - for each item: non-empty summary, non-empty sources, no 'error'
    """
    if not isinstance(data, dict):
        return False, "not a dict"

    results = data.get("results")
    if not isinstance(results, list) or not results:
        return False, "missing/empty results"

    for i, item in enumerate(results):
        if not isinstance(item, dict):
            return False, f"results[{i}] not a dict"

        if item.get("error"):
            # Check if it is the specific known Google error, or just any error? 
            # The user logic handles 'error' field presence as invalid.
            return False, f"results[{i}] has error"

        # Check Summary
        summary = (item.get("summary") or "").strip()
        if len(summary) < MIN_SUMMARY_LEN:
            return False, f"results[{i}] summary too short ({len(summary)})"

        # Check Sources
        sources = item.get("sources")
        if not isinstance(sources, list) or len(sources) < MIN_SOURCES_LEN:
             # Some topics might validly have 0 sources if no news found? 
             # But user logic says strict check.
            return False, f"results[{i}] sources too few ({0 if not isinstance(sources, list) else len(sources)})"
            
        # Optional: Check Metadata Article Count
        meta = item.get("metadata") or {}
        if isinstance(meta, dict) and "articleCount" in meta:
             try:
                 if int(meta.get("articleCount") or 0) <= 0:
                     return False, f"results[{i}] articleCount <= 0"
             except: pass

    return True, "ok"

def _is_api_key_invalid_report(data: Any) -> bool:
    """
    Detects the specific "API key not valid / API_KEY_INVALID" failure.
    """
    if not isinstance(data, dict):
        return False
    results = data.get("results")
    if not isinstance(results, list) or not results:
        return False

    for item in results:
        if not isinstance(item, dict):
            continue
        err = item.get("error")
        if not err:
            continue

        # String signature
        if isinstance(err, str):
            low = err.lower()
            if "api key not valid" in low or "api_key_invalid" in low:
                return True
            try:
                err_obj = json.loads(err)
            except:
                err_obj = None
        else:
            # Already object?
            err_obj = err

        if isinstance(err_obj, dict):
            e = err_obj.get("error") or {}
            msg = (e.get("message") or "").lower()
            status = (e.get("status") or "").upper()
            if "api key not valid" in msg:
                return True
            if status in {"INVALID_ARGUMENT", "PERMISSION_DENIED"}:
                details = e.get("details") or []
                for d in details:
                    if isinstance(d, dict):
                        # check metadata reason
                        reason = (d.get("reason") or "").upper()
                        if reason == "API_KEY_INVALID":
                            return True
                        meta = d.get("metadata") or {}
                        for v in meta.values():
                            if isinstance(v, str) and "api_key_invalid" in v.lower():
                                return True
    return False

async def _read_pre_texts(page: Page) -> List[str]:
    # Extract content of all pre tags
    return await page.evaluate(
        """() => Array.from(document.querySelectorAll('pre'))
              .map(el => (el.textContent || '').trim())
              .filter(t => t.length > 0)"""
    )

async def inspect_page(page: Page) -> Inspection:
    pre_texts = await _read_pre_texts(page)
    loading_present = any(t.lower().startswith("loading analysis") for t in pre_texts)

    for t in pre_texts:
        if t.lower().startswith("loading analysis"):
            continue

        # Basic JSON signature check
        if not (t.startswith("{") and '"results"' in t):
            continue

        try:
            data = json.loads(t)
        except json.JSONDecodeError:
            continue

        ok, reason = is_final_report(data)
        if ok:
            return Inspection(final_data=data, loading_present=loading_present) # found good data
        
        # Check for specific failure patterns
        if _is_api_key_invalid_report(data):
            return Inspection(final_data=None, loading_present=loading_present, api_key_invalid=True)
            
    return Inspection(final_data=None, loading_present=loading_present)


def with_cache_buster(url: str) -> str:
    cb = int(time.time() * 1000)
    if "#" in url:
        base, frag = url.split("#", 1)
        sep = "&" if "?" in base else "?"
        return f"{base}{sep}cb={cb}#{frag}"
    sep = "&" if "?" in url else "?"
    return f"{url}{sep}cb={cb}"


async def reload_page(page: Page, reason: str, reload_no: int, url: str) -> None:
    logger.warning(f"Reload #{reload_no}: reason='{reason}'. Sleeping 5s...")
    await asyncio.sleep(5)
    
    try:
        await page.reload(wait_until="domcontentloaded", timeout=60000)
    except Exception as e:
        logger.warning(f"Reload failed ({e}); navigating with cache buster.")
        await page.goto(with_cache_buster(url), wait_until="domcontentloaded", timeout=60000)
    
    try:
        await page.wait_for_selector("pre", timeout=20000)
    except:
        pass


async def fetch_forecast(
    countries: str,
    topics: str,
    language: str,
    time_horizon: str,
    depth: str
) -> Optional[Dict[str, Any]]:
    """
    Fetches the forecast using Playwright with advanced retry/reload logic.
    User provided robust logic adapted here.
    """
    base = API_BASE_URL.rstrip('/')
    fragment = f"/news-json?countries={countries}&topics={topics}&language={language}&time_horizon={time_horizon}&depth={depth}"
    url = f"{base}/#{fragment}"
    
    # Logic constants
    MAX_RELOADS = 2
    LOADING_STUCK_SEC = 180
    
    logger.info(f"Launching Headless Browser to fetch: {url}")

    async with async_playwright() as p:
        try:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
            )
            page = await context.new_page()
            
            # Setup console debugging
            page.on("console", lambda msg: logger.debug(f"Console: {msg.text}"))
            
            # Navigation
            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=60000)
            except Exception as e:
                logger.error(f"Navigation failed: {e}")
                return None
                
            # Initial wait for pre
            try:
                 await page.wait_for_selector("pre", timeout=20000)
            except:
                 logger.warning("No <pre> found quickly.")
            
            overall_start = time.time()
            phase_start = overall_start
            reloads_done = 0
            
            # Polling Loop
            while True:
                overall_elapsed = time.time() - overall_start
                # Global timeout check
                if overall_elapsed > (REQUEST_TIMEOUT_SEC + 60): # Give it slightly more than pure request timeout
                    logger.error("Global fetch timeout exceeded.")
                    # debug screenshot
                    try: await page.screenshot(path="timeout_screenshot.png") 
                    except: pass
                    return None
                
                insp = await inspect_page(page)
                
                if insp.final_data:
                    logger.info("Successfully retrieved FINAL JSON.")
                    return insp.final_data
                
                if insp.api_key_invalid:
                    if reloads_done < MAX_RELOADS:
                        reloads_done += 1
                        await reload_page(page, "API_KEY_INVALID detected", reloads_done, url)
                        phase_start = time.time()
                        continue
                    else:
                        logger.error("API Error: API Key Invalid persisted after reloads.")
                        return None
                        
                phase_elapsed = time.time() - phase_start
                if insp.loading_present and phase_elapsed >= LOADING_STUCK_SEC:
                    if reloads_done < MAX_RELOADS:
                        reloads_done += 1
                        await reload_page(page, f"Stuck on Loading for {int(phase_elapsed)}s", reloads_done, url)
                        phase_start = time.time()
                        continue
                
                # Wait before next poll
                await asyncio.sleep(2)
                
        except Exception as e:
            logger.error(f"Playwright Critical Error: {e}")
            return None


