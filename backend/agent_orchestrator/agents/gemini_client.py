"""
Shared Gemini client with automatic retry on quota errors.
All agents import `call_gemini` instead of calling generate_content_async directly.
"""
import asyncio
import logging
import os

import google.generativeai as genai

logger = logging.getLogger(__name__)

_model_cache: dict = {}


def get_gemini_model(model: str):
    if model not in _model_cache:
        api_key = os.getenv("GOOGLE_API_KEY")
        if api_key:
            genai.configure(api_key=api_key)
        _model_cache[model] = genai.GenerativeModel(model)
    return _model_cache[model]


async def call_gemini(prompt: str, model: str = None, max_retries: int = 2) -> str | None:
    """
    Call Gemini with retry on per-minute quota errors.
    Skips retry on daily/project quota exhaustion (no point waiting).
    Returns response text or None if unavailable.
    """
    if model is None:
        model = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")

    gemini = get_gemini_model(model)

    for attempt in range(max_retries):
        try:
            response = await gemini.generate_content_async(prompt)
            return response.text.strip()
        except Exception as e:
            err = str(e)
            is_rate_limit = "429" in err or "rate" in err.lower()
            is_daily_quota = "per_day" in err.lower() or "PerDay" in err or "free_tier_input_token" in err.lower()

            if is_daily_quota:
                # Daily quota exhausted — no point retrying, fall back immediately
                logger.warning("Gemini daily quota exhausted — using fallback decision")
                return None
            elif is_rate_limit and attempt < max_retries - 1:
                wait = 30  # wait 30s on per-minute rate limit
                logger.warning(f"Gemini rate limit (attempt {attempt+1}), retrying in {wait}s...")
                await asyncio.sleep(wait)
            else:
                logger.warning(f"Gemini call failed: {e}")
                return None

    return None
