"""
weather_control.py — Live spoken weather for ORION MK2
────────────────────────────────────────────────────────
Uses Open-Meteo (free, no API key) + Open-Meteo Geocoding API.
pip install requests
────────────────────────────────────────────────────────
"""

import requests

# ── WMO weather code → human description ─────────────────
_WMO_CODES = {
    0:  "clear skies",
    1:  "mainly clear",
    2:  "partly cloudy",
    3:  "overcast",
    45: "foggy",
    48: "icy fog",
    51: "light drizzle",
    53: "moderate drizzle",
    55: "heavy drizzle",
    61: "light rain",
    63: "moderate rain",
    65: "heavy rain",
    71: "light snow",
    73: "moderate snow",
    75: "heavy snow",
    77: "snow grains",
    80: "light showers",
    81: "moderate showers",
    82: "violent showers",
    85: "light snow showers",
    86: "heavy snow showers",
    95: "thunderstorms",
    96: "thunderstorms with hail",
    99: "severe thunderstorms with heavy hail",
}


def _geocode(city: str) -> tuple[float, float, str]:
    """
    Resolve a city name to (latitude, longitude, display_name).
    Raises WeatherError if not found.
    """
    try:
        r = requests.get(
            "https://geocoding-api.open-meteo.com/v1/search",
            params={"name": city, "count": 1, "language": "en", "format": "json"},
            timeout=5,
        )
        r.raise_for_status()
        results = r.json().get("results")
        if not results:
            raise WeatherError(f"Could not find a location called '{city}'.")
        top = results[0]
        return top["latitude"], top["longitude"], top.get("name", city)
    except requests.RequestException as e:
        raise WeatherError(f"Geocoding request failed: {e}") from e


def get_weather(city: str = "Birmingham") -> dict:
    """
    Fetch current weather for a city.
    Returns a dict with temperature, feels_like, condition, wind_speed, humidity.
    """
    try:
        lat, lon, display_name = _geocode(city)

        r = requests.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude":               lat,
                "longitude":              lon,
                "current":                [
                    "temperature_2m",
                    "apparent_temperature",
                    "weathercode",
                    "windspeed_10m",
                    "relativehumidity_2m",
                ],
                "temperature_unit":       "celsius",
                "windspeed_unit":         "mph",
                "timezone":               "Europe/London",
            },
            timeout=5,
        )
        r.raise_for_status()
        data    = r.json()
        current = data["current"]

        code      = current.get("weathercode", 0)
        condition = _WMO_CODES.get(code, "unknown conditions")

        return {
            "city":        display_name,
            "temperature": round(current["temperature_2m"]),
            "feels_like":  round(current["apparent_temperature"]),
            "condition":   condition,
            "wind_speed":  round(current["windspeed_10m"]),
            "humidity":    current.get("relativehumidity_2m", 0),
        }

    except requests.RequestException as e:
        raise WeatherError(f"Weather request failed: {e}") from e


def get_forecast(city: str = "Birmingham", days: int = 3) -> list[dict]:
    """
    Fetch a daily forecast for the next `days` days.
    Returns a list of dicts with date, max_temp, min_temp, condition.
    """
    try:
        lat, lon, display_name = _geocode(city)
        days = min(days, 7)

        r = requests.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude":         lat,
                "longitude":        lon,
                "daily":            ["weathercode", "temperature_2m_max", "temperature_2m_min"],
                "temperature_unit": "celsius",
                "timezone":         "Europe/London",
                "forecast_days":    days,
            },
            timeout=5,
        )
        r.raise_for_status()
        data  = r.json()
        daily = data["daily"]

        forecast = []
        for i in range(days):
            code = daily["weathercode"][i]
            forecast.append({
                "city":     display_name,
                "date":     daily["time"][i],
                "max_temp": round(daily["temperature_2m_max"][i]),
                "min_temp": round(daily["temperature_2m_min"][i]),
                "condition": _WMO_CODES.get(code, "unknown conditions"),
            })
        return forecast

    except requests.RequestException as e:
        raise WeatherError(f"Forecast request failed: {e}") from e


def format_weather_speech(data: dict) -> str:
    """Turn a weather dict into a natural spoken sentence."""
    return (
        f"Currently in {data['city']}: {data['condition']}, "
        f"{data['temperature']} degrees Celsius, "
        f"feels like {data['feels_like']}. "
        f"Wind speed is {data['wind_speed']} miles per hour "
        f"with {data['humidity']} percent humidity."
    )


def format_forecast_speech(forecast: list[dict]) -> str:
    """Turn a forecast list into a spoken summary."""
    if not forecast:
        return "No forecast data available, sir."
    lines = [f"Here is the {len(forecast)}-day forecast for {forecast[0]['city']}."]
    for day in forecast:
        lines.append(
            f"{day['date']}: {day['condition']}, "
            f"high of {day['max_temp']} and low of {day['min_temp']} degrees."
        )
    return " ".join(lines)



class WeatherError(Exception):
    """Raised when a weather operation fails."""
