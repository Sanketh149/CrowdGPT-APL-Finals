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


async def call_gemini(prompt: str, model: str = None, max_retries: int = 3) -> str | None:
    """
    Call Gemini with exponential backoff on quota/rate-limit errors.
    Returns response text or None if all retries fail.
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
            is_quota = "quota" in err.lower() or "429" in err or "rate" in err.lower()
            if is_quota and attempt < max_retries - 1:
                wait = 15 * (attempt + 1)  # 15s, 30s, 45s
                logger.warning(f"Gemini quota hit (attempt {attempt+1}), retrying in {wait}s...")
                await asyncio.sleep(wait)
            else:
                logger.warning(f"Gemini call failed: {e}")
                return None

    return None
