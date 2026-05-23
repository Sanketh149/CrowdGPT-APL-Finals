"""
Weather Context Agent
Fetches current weather from the Open-Meteo API for the stadium location
and returns routing impact assessment.
"""

import logging
from datetime import datetime
from typing import Any, Dict

import httpx
from google.adk.agents import LlmAgent

from tools.sensor_tools import get_zone_density_tool

logger = logging.getLogger(__name__)

# Narendra Modi Stadium, Ahmedabad coordinates
STADIUM_LAT = 23.0920
STADIUM_LON = 72.5934

WEATHER_CONTEXT_PROMPT = """
You are the Weather Context Specialist for CrowdGuard Command.

Your job:
1. Fetch live weather data for the stadium location.
2. Assess how current conditions affect crowd behaviour and routing.
3. Flag conditions that increase risk: heavy rain, heat index > 40°C, strong winds.
4. Recommend covered exit routing if rain is detected.
5. Flag heat stress risk if temperature + humidity are extreme.

Output JSON:
{
  "temperature_c": float,
  "humidity_pct": float,
  "wind_speed_kmh": float,
  "precipitation_mm": float,
  "weather_code": int,
  "conditions": str,
  "heat_index": float,
  "routing_impact": "none|minor|moderate|severe",
  "recommendation": str
}
"""

OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"


class WeatherContextAgent:
    """Fetches weather and returns routing impact for stadium operations."""

    def __init__(self, model: str = "gemini-1.5-pro"):
        self.model = model
        self.agent = LlmAgent(
            name="weather_context_agent",
            model=model,
            description="Fetches weather data and assesses routing impact",
            instruction=WEATHER_CONTEXT_PROMPT,
            tools=[get_zone_density_tool],
        )
        self._cached_weather: Dict = {}
        self._cache_ts: float = 0.0

    async def analyze(self, context: Dict[str, Any]) -> Dict[str, Any]:
        timestamp = datetime.utcnow().isoformat()

        try:
            weather = await self._fetch_weather()
            heat_index = self._compute_heat_index(
                weather["temperature_c"], weather["humidity_pct"]
            )
            routing_impact = self._assess_routing_impact(weather, heat_index)
            recommendation = self._build_recommendation(weather, heat_index, routing_impact)

            return {
                "agent": "weather_context",
                "timestamp": timestamp,
                "decision": (
                    f"{weather['conditions']} — {weather['temperature_c']}°C, "
                    f"routing impact: {routing_impact}"
                ),
                "confidence": 0.90,
                "metadata": {
                    **weather,
                    "heat_index": round(heat_index, 1),
                    "routing_impact": routing_impact,
                    "recommendation": recommendation,
                },
            }

        except Exception as e:
            logger.warning(f"WeatherContextAgent: API unavailable, using simulated data: {e}")
            return self._simulated_response(timestamp)

    async def _fetch_weather(self) -> Dict:
        """Call Open-Meteo API for current conditions."""
        import time
        now = time.time()

        # Cache for 5 minutes to avoid hammering the API
        if self._cached_weather and (now - self._cache_ts) < 300:
            return self._cached_weather

        params = {
            "latitude": STADIUM_LAT,
            "longitude": STADIUM_LON,
            "current": [
                "temperature_2m",
                "relative_humidity_2m",
                "wind_speed_10m",
                "precipitation",
                "weather_code",
            ],
            "timezone": "Asia/Kolkata",
        }

        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.get(OPEN_METEO_URL, params=params)
            resp.raise_for_status()
            data = resp.json()

        current = data["current"]
        weather = {
            "temperature_c": current.get("temperature_2m", 32.0),
            "humidity_pct": current.get("relative_humidity_2m", 55.0),
            "wind_speed_kmh": current.get("wind_speed_10m", 10.0),
            "precipitation_mm": current.get("precipitation", 0.0),
            "weather_code": current.get("weather_code", 0),
            "conditions": self._decode_weather_code(current.get("weather_code", 0)),
        }
        self._cached_weather = weather
        self._cache_ts = now
        return weather

    @staticmethod
    def _decode_weather_code(code: int) -> str:
        if code == 0:
            return "Clear sky"
        if code in (1, 2, 3):
            return "Partly cloudy"
        if code in (45, 48):
            return "Foggy"
        if code in range(51, 68):
            return "Drizzle / Rain"
        if code in range(71, 78):
            return "Snow"
        if code in range(80, 83):
            return "Rain showers"
        if code in range(95, 100):
            return "Thunderstorm"
        return "Unknown"

    @staticmethod
    def _compute_heat_index(temp_c: float, humidity_pct: float) -> float:
        """Steadman heat index approximation."""
        T = temp_c
        H = humidity_pct
        hi = (
            -8.78469475556
            + 1.61139411 * T
            + 2.33854883889 * H
            - 0.14611605 * T * H
            - 0.012308094 * T**2
            - 0.0164248277778 * H**2
            + 0.002211732 * T**2 * H
            + 0.00072546 * T * H**2
            - 0.000003582 * T**2 * H**2
        )
        return max(hi, temp_c)

    @staticmethod
    def _assess_routing_impact(weather: Dict, heat_index: float) -> str:
        if weather["precipitation_mm"] > 10 or weather["wind_speed_kmh"] > 60:
            return "severe"
        if weather["precipitation_mm"] > 2 or heat_index > 42 or weather["wind_speed_kmh"] > 40:
            return "moderate"
        if heat_index > 38 or weather["precipitation_mm"] > 0.5:
            return "minor"
        return "none"

    @staticmethod
    def _build_recommendation(weather: Dict, heat_index: float, impact: str) -> str:
        if impact == "severe":
            return (
                "SEVERE weather — route all crowds to covered concourses, "
                "activate covered emergency exits E1-E4"
            )
        if impact == "moderate":
            if weather["precipitation_mm"] > 2:
                return "Rain detected — prioritise covered exits G3, G5, G7; deploy umbrellas"
            return f"Heat stress risk (HI={heat_index:.0f}°C) — open cooling zones, hydration stations"
        if impact == "minor":
            return "Monitor conditions — minor impact on crowd comfort"
        return "Weather conditions nominal — no routing adjustments required"

    def _simulated_response(self, timestamp: str) -> Dict:
        """Return realistic simulated weather for Ahmedabad in April."""
        return {
            "agent": "weather_context",
            "timestamp": timestamp,
            "decision": "Clear sky — 36°C, routing impact: minor",
            "confidence": 0.7,
            "metadata": {
                "temperature_c": 36.0,
                "humidity_pct": 38.0,
                "wind_speed_kmh": 12.0,
                "precipitation_mm": 0.0,
                "weather_code": 0,
                "conditions": "Clear sky",
                "heat_index": 37.5,
                "routing_impact": "minor",
                "recommendation": "Heat stress monitoring — deploy hydration stations at G1, G4, G8",
                "source": "simulated",
            },
        }
