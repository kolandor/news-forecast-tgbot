import httpx
import logging
import asyncio
from typing import Dict, Any, Optional
from config import API_BASE_URL, REQUEST_TIMEOUT_SEC

logger = logging.getLogger(__name__)

async def fetch_forecast(
    countries: str,
    topics: str,
    language: str,
    time_horizon: str,
    depth: str
) -> Optional[Dict[str, Any]]:
    """
    Fetches the forecast from the API with retries.
    Returns the JSON dict on success, or None on failure (after retries).
    Raises errors if critical.
    """
    url = f"{API_BASE_URL.rstrip('/')}/news-json"
    
    # NOTE: The User provided an example URL with '/#/news-json'.
    # However, standard HTTP clients (like httpx) do not send the fragment (#...) to the server.
    # The server logs show success with '/news-json' (without hash). 
    # If the user absolutely insists on sending the hash to the server, it would need to be percent-encoded (%23).
    # But given the successful logs, we stay with the standard URL construction.
    # To fix the user's confusion, we strictly use the path without hash as it works.
    
    params = {
        "countries": countries,
        "topics": topics,
        "language": language,
        "time_horizon": time_horizon,
        "depth": depth
    }

    # Retry policy: 3 retries (5s, 15s, 30s)
    backoffs = [5, 15, 30]
    
    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT_SEC) as client:
        for attempt, sleep_time in enumerate(backoffs + [None]):
            try:
                logger.info(f"API Request attempt {attempt+1} to {url} with params {params}")
                response = await client.get(url, params=params)
                
                if response.status_code == 200:
                    try:
                        data = response.json()
                        if "results" not in data:
                            logger.error(f"API response missing 'results' key: {data.keys()}")
                            return None
                        return data
                    except ValueError:
                        logger.error("API returned invalid JSON")
                        return None
                        
                elif response.status_code >= 500:
                    logger.warning(f"API 5xx error: {response.status_code}")
                    # Allow retry
                else:
                    # Client error (4xx) - usually no point retrying unless 429 often?
                    # But prompt specifically says retries on 5xx.
                    logger.error(f"API Client error: {response.status_code} - {response.text}")
                    return None
                    
            except httpx.RequestError as e:
                logger.warning(f"API Request error: {e}")
            
            # If we are here, we failed. Check if we should retry.
            if sleep_time is not None:
                logger.info(f"Retrying in {sleep_time} seconds...")
                await asyncio.sleep(sleep_time)
            else:
                logger.error("All retries exhausted.")
                return None
    return None
