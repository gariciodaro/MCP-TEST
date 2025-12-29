from typing import Any

import httpx
from mcp.server.fastmcp import FastMCP

# Initialize FastMCP server
mcp = FastMCP("weather")

# Constants
NWS_API_BASE = "https://api.weather.gov"
USER_AGENT = "weather-app/1.0"

# Supported US state codes
US_STATES = {
    "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas",
    "CA": "California", "CO": "Colorado", "CT": "Connecticut", "DE": "Delaware",
    "FL": "Florida", "GA": "Georgia", "HI": "Hawaii", "ID": "Idaho",
    "IL": "Illinois", "IN": "Indiana", "IA": "Iowa", "KS": "Kansas",
    "KY": "Kentucky", "LA": "Louisiana", "ME": "Maine", "MD": "Maryland",
    "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota", "MS": "Mississippi",
    "MO": "Missouri", "MT": "Montana", "NE": "Nebraska", "NV": "Nevada",
    "NH": "New Hampshire", "NJ": "New Jersey", "NM": "New Mexico", "NY": "New York",
    "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio", "OK": "Oklahoma",
    "OR": "Oregon", "PA": "Pennsylvania", "RI": "Rhode Island", "SC": "South Carolina",
    "SD": "South Dakota", "TN": "Tennessee", "TX": "Texas", "UT": "Utah",
    "VT": "Vermont", "VA": "Virginia", "WA": "Washington", "WV": "West Virginia",
    "WI": "Wisconsin", "WY": "Wyoming"
}

# Example cities with coordinates
EXAMPLE_CITIES = {
    "New York": {"lat": 40.7128, "lon": -74.0060, "state": "NY"},
    "Los Angeles": {"lat": 34.0522, "lon": -118.2437, "state": "CA"},
    "Chicago": {"lat": 41.8781, "lon": -87.6298, "state": "IL"},
    "Houston": {"lat": 29.7604, "lon": -95.3698, "state": "TX"},
    "Phoenix": {"lat": 33.4484, "lon": -112.0740, "state": "AZ"},
    "Seattle": {"lat": 47.6062, "lon": -122.3321, "state": "WA"},
    "Miami": {"lat": 25.7617, "lon": -80.1918, "state": "FL"},
    "Denver": {"lat": 39.7392, "lon": -104.9903, "state": "CO"},
}


# ============== RESOURCES ==============
# Resources are read-only data that can be fetched by URI

@mcp.resource("weather://supported-states")
def get_supported_states() -> str:
    """List of all supported US state codes for weather alerts."""
    lines = ["Supported US State Codes for Weather Alerts:", ""]
    for code, name in sorted(US_STATES.items()):
        lines.append(f"  {code}: {name}")
    return "\n".join(lines)


@mcp.resource("weather://example-cities")
def get_example_cities() -> str:
    """Example cities with their coordinates for weather forecasts."""
    lines = ["Example Cities with Coordinates:", ""]
    for city, data in EXAMPLE_CITIES.items():
        lines.append(f"  {city}:")
        lines.append(f"    Latitude: {data['lat']}")
        lines.append(f"    Longitude: {data['lon']}")
        lines.append(f"    State: {data['state']}")
        lines.append("")
    return "\n".join(lines)


@mcp.resource("weather://api-info")
def get_api_info() -> str:
    """Information about the National Weather Service API used by this server."""
    return """National Weather Service (NWS) API Information
    
API Base URL: https://api.weather.gov
Documentation: https://www.weather.gov/documentation/services-web-api

Features:
- Weather forecasts by latitude/longitude
- Active weather alerts by state
- Free to use, no API key required
- US locations only

Rate Limits:
- No strict rate limits, but be respectful
- Include User-Agent header (we use: weather-app/1.0)

Data Format:
- Returns GeoJSON format
- Forecasts include temperature, wind, and detailed descriptions
- Alerts include severity, description, and instructions
"""


async def make_nws_request(url: str) -> dict[str, Any] | None:
    """Make a request to the NWS API with proper error handling."""
    headers = {"User-Agent": USER_AGENT, "Accept": "application/geo+json"}
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, headers=headers, timeout=30.0)
            response.raise_for_status()
            return response.json()
        except Exception:
            return None


def format_alert(feature: dict) -> str:
    """Format an alert feature into a readable string."""
    props = feature["properties"]
    return f"""
Event: {props.get("event", "Unknown")}
Area: {props.get("areaDesc", "Unknown")}
Severity: {props.get("severity", "Unknown")}
Description: {props.get("description", "No description available")}
Instructions: {props.get("instruction", "No specific instructions provided")}
"""


@mcp.tool()
async def get_alerts(state: str) -> str:
    """Get weather alerts for a US state.

    Args:
        state: Two-letter US state code (e.g. CA, NY)
    """
    url = f"{NWS_API_BASE}/alerts/active/area/{state}"
    data = await make_nws_request(url)

    if not data or "features" not in data:
        return "Unable to fetch alerts or no alerts found."

    if not data["features"]:
        return "No active alerts for this state."

    alerts = [format_alert(feature) for feature in data["features"]]
    return "\n---\n".join(alerts)


@mcp.tool()
async def get_forecast(latitude: float, longitude: float) -> str:
    """Get weather forecast for a location.

    Args:
        latitude: Latitude of the location
        longitude: Longitude of the location
    """
    # First get the forecast grid endpoint
    points_url = f"{NWS_API_BASE}/points/{latitude},{longitude}"
    points_data = await make_nws_request(points_url)

    if not points_data:
        return "Unable to fetch forecast data for this location."

    # Get the forecast URL from the points response
    forecast_url = points_data["properties"]["forecast"]
    forecast_data = await make_nws_request(forecast_url)

    if not forecast_data:
        return "Unable to fetch detailed forecast."

    # Format the periods into a readable forecast
    periods = forecast_data["properties"]["periods"]
    forecasts = []
    for period in periods[:5]:  # Only show next 5 periods
        forecast = f"""
{period["name"]}:
Temperature: {period["temperature"]}°{period["temperatureUnit"]}
Wind: {period["windSpeed"]} {period["windDirection"]}
Forecast: {period["detailedForecast"]}
"""
        forecasts.append(forecast)

    return "\n---\n".join(forecasts)


def main():
    # Initialize and run the server
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()