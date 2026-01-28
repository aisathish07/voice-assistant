"""
skills/weather_skill.py
──────────────────────────────────────────────
Weather Skill for Jarvis
Fetches real-time weather via Open-Meteo API, with offline fallback.
"""

from skills.base_skill import BaseSkill
import asyncio
import aiohttp
import datetime
import json

class Skill(BaseSkill):
    name = "weather"
    keywords = ["weather", "temperature", "forecast", "rain", "sunny", "wind"]

    async def handle(self, text, jarvis):
        text = text.lower().strip()
        # Try to extract a city name (very simple pattern)
        city = None
        for token in text.split():
            if token.istitle() or token in ["delhi", "mumbai", "london", "new", "york"]:
                city = token.capitalize()
                break
        city = self.config.get("default_location", "your location")
        units = self.config.get("units", "celsius")

        try:
            weather_data = await self.get_weather(city)
            return self.format_weather(city, weather_data)
        except Exception as e:
            # Offline fallback using the model (if available)
            try:
                prompt = f"Give a short weather-style sentence for {city} (fictional, no data)."
                response = await jarvis.core.process_query(prompt, speak=False)
                return response
            except Exception:
                return f"Could not get weather info ({e})."

    async def get_weather(self, city: str) -> dict:
        """Fetch weather data from Open-Meteo."""
        # Example lat/long table (expand later or use geocoding)
        coords = {
            "Delhi": (28.61, 77.23),
            "Mumbai": (19.07, 72.87),
            "London": (51.51, -0.13),
            "New": (40.71, -74.01),
            "York": (40.71, -74.01),
        }
        lat, lon = coords.get(city, (28.61, 77.23))
        temperature_unit = self.config.get("units", "celsius")
        url = (
            f"https://api.open-meteo.com/v1/forecast?"
            f"latitude={lat}&longitude={lon}"
            f"&current_weather=true"
            f"&daily=temperature_2m_max,temperature_2m_min,precipitation_sum"
            f"&temperature_unit={temperature_unit}"
            f"&timezone=auto"
        )

        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=5) as resp:
                if resp.status != 200:
                    raise RuntimeError(f"API status {resp.status}")
                return await resp.json()

    def format_weather(self, city: str, data: dict) -> str:
        """Return formatted weather string."""
        try:
            current = data["current_weather"]
            temp = current.get("temperature")
            wind = current.get("windspeed")
            time_str = current.get("time", "")
            timestamp = datetime.datetime.fromisoformat(time_str)
            units = self.config.get("units", "celsius")
            temp_unit = "°C" if units == "celsius" else "°F"

            summary = (
                f"The current temperature in {city} is {temp}{temp_unit} "
                f"with winds around {wind} km/h (as of {timestamp.strftime('%H:%M')})."
            )
            if "daily" in data:
                temps = data["daily"]["temperature_2m_max"]
                min_t = data["daily"]["temperature_2m_min"]
                rain = data["daily"]["precipitation_sum"]
                if temps:
                    summary += f" Today's high is {temps[0]}{temp_unit}, low {min_t[0]}{temp_unit}."
                    if rain and rain[0] > 0:
                        summary += f" Expect some rain ({rain[0]} mm)."
            return summary
        except Exception:
            return f"Weather data unavailable for {city}."
