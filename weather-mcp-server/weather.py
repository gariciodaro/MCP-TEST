from typing import Any
from dataclasses import dataclass

import httpx
from mcp.server.fastmcp import FastMCP, Context

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


@mcp.resource("weather://use-cases")
def get_use_cases() -> str:
    """Example use cases and sample prompts for this weather MCP server."""
    return """Weather MCP Server - Use Cases & Examples

═══════════════════════════════════════════════════════════
🌤️  USE CASE 1: Daily Weather Check
═══════════════════════════════════════════════════════════
Scenario: Check the weather before planning your day

Example prompts:
  • "What's the weather forecast for New York City?"
  • "Get the forecast for coordinates 40.7128, -74.0060"
  • "What will the weather be like in Seattle this week?"

Tool used: get_forecast(latitude, longitude)

═══════════════════════════════════════════════════════════
⚠️  USE CASE 2: Severe Weather Monitoring
═══════════════════════════════════════════════════════════
Scenario: Check for weather alerts before traveling or for safety

Example prompts:
  • "Are there any weather alerts in California?"
  • "Check for severe weather warnings in TX"
  • "What weather alerts are active in Florida right now?"

Tool used: get_alerts(state)

═══════════════════════════════════════════════════════════
✈️  USE CASE 3: Travel Planning
═══════════════════════════════════════════════════════════
Scenario: Planning a trip and need weather info for multiple locations

Example prompts:
  • "I'm traveling to Miami next week. What's the forecast?"
  • "Compare weather between Denver and Phoenix"
  • "Check if there are any weather alerts for my road trip through TX, OK, and KS"

Tools used: get_forecast + get_alerts

═══════════════════════════════════════════════════════════
🏠  USE CASE 4: Event Planning
═══════════════════════════════════════════════════════════
Scenario: Planning outdoor events and need reliable weather data

Example prompts:
  • "What's the weather forecast for Chicago for an outdoor wedding?"
  • "Will it rain in Los Angeles this weekend?"
  • "Check weather conditions for a hiking trip in Colorado"

Tool used: get_forecast(latitude, longitude)

═══════════════════════════════════════════════════════════
📊  USE CASE 5: Integration with Other Systems
═══════════════════════════════════════════════════════════
Scenario: Combining weather data with other MCP servers

Example integrations:
  • Calendar + Weather: "What's the weather for my meetings tomorrow?"
  • Maps + Weather: "Weather along my route from NYC to Boston"
  • News + Weather: "Summarize weather-related news for California"

This demonstrates MCP's power to combine multiple data sources!

═══════════════════════════════════════════════════════════
💡  TIPS FOR BEST RESULTS
═══════════════════════════════════════════════════════════
  • Use two-letter state codes for alerts (CA, NY, TX, etc.)
  • Provide coordinates for precise forecast locations
  • Check the 'example-cities' resource for coordinate references
  • US locations only (NWS API limitation)
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


# ============== ELICITATION DEMO ==============
# Tool that demonstrates elicitation - asking user for input mid-execution

from pydantic import BaseModel

class TripDetails(BaseModel):
    """Details for trip planning"""
    travel_date: str
    num_days: int
    activities: str  # "outdoor", "indoor", or "mixed"


@mcp.tool()
async def plan_trip(destination: str, ctx: Context) -> str:
    """Plan a trip with weather-aware recommendations.
    
    This tool demonstrates MCP elicitation by asking the user for
    additional details mid-execution.
    
    Args:
        destination: City name for the trip (e.g., "New York", "Denver")
    """
    # Check if destination is in our known cities
    city_data = EXAMPLE_CITIES.get(destination)
    if not city_data:
        available = ", ".join(EXAMPLE_CITIES.keys())
        return f"Sorry, '{destination}' is not in our database. Available cities: {available}"
    
    # Step 1: Ask user for trip details via elicitation
    result = await ctx.elicit(
        message=f"Planning trip to {destination}. Please provide your trip details:",
        schema=TripDetails
    )
    
    if result.action == "decline":
        return "Trip planning cancelled - you declined to provide details."
    
    if result.action == "cancel":
        return "Trip planning cancelled."
    
    # User accepted - get their data
    trip_data = result.data
    
    # Step 2: Fetch weather for the destination
    lat, lon = city_data["lat"], city_data["lon"]
    state = city_data["state"]
    
    # Get forecast
    points_url = f"{NWS_API_BASE}/points/{lat},{lon}"
    points_data = await make_nws_request(points_url)
    
    forecast_text = "Weather data unavailable"
    if points_data:
        forecast_url = points_data["properties"]["forecast"]
        forecast_data = await make_nws_request(forecast_url)
        if forecast_data:
            periods = forecast_data["properties"]["periods"][:trip_data.num_days * 2]  # day + night per day
            forecast_text = "\n".join([
                f"  • {p['name']}: {p['temperature']}°{p['temperatureUnit']}, {p['shortForecast']}"
                for p in periods
            ])
    
    # Get alerts
    alerts_url = f"{NWS_API_BASE}/alerts/active/area/{state}"
    alerts_data = await make_nws_request(alerts_url)
    alerts_text = "No active alerts"
    if alerts_data and alerts_data.get("features"):
        alerts_text = "\n".join([
            f"  ⚠️ {f['properties']['event']}: {f['properties']['headline']}"
            for f in alerts_data["features"][:3]
        ])
    
    # Step 3: Generate recommendations based on weather + preferences
    activity_rec = ""
    if trip_data.activities == "outdoor":
        activity_rec = "Since you prefer outdoor activities, check the forecast for clear days."
    elif trip_data.activities == "indoor":
        activity_rec = "For indoor activities, weather won't affect your plans much."
    else:
        activity_rec = "With mixed activities, have backup indoor plans for bad weather days."
    
    return f"""
🗺️ Trip Plan for {destination}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📅 Travel Date: {trip_data.travel_date}
⏱️ Duration: {trip_data.num_days} days
🎯 Activity Preference: {trip_data.activities}

🌤️ Weather Forecast:
{forecast_text}

🚨 Weather Alerts:
{alerts_text}

💡 Recommendation:
{activity_rec}

Have a great trip! 🧳
"""


# ============== PROMPTS ==============
# Prompts are structured templates that guide user interactions

@mcp.prompt()
def check_city_weather(city: str) -> str:
    """Get a weather forecast for a major US city.
    
    Args:
        city: Name of a major US city (e.g., New York, Los Angeles, Chicago)
    """
    city_data = EXAMPLE_CITIES.get(city)
    if city_data:
        return f"""Please get the weather forecast for {city}.
        
Use the get_forecast tool with these coordinates:
- Latitude: {city_data['lat']}
- Longitude: {city_data['lon']}

After getting the forecast, provide a friendly summary of:
1. Current conditions
2. Temperature trends
3. Any notable weather to be aware of"""
    else:
        available = ", ".join(EXAMPLE_CITIES.keys())
        return f"""The city "{city}" is not in our quick-reference list.

Available cities with pre-loaded coordinates: {available}

Please either:
1. Choose one of the available cities above
2. Or provide specific latitude/longitude coordinates for {city}"""


@mcp.prompt()
def check_state_alerts(state: str) -> str:
    """Check weather alerts for a US state.
    
    Args:
        state: Two-letter US state code (e.g., CA, NY, TX)
    """
    state_upper = state.upper()
    state_name = US_STATES.get(state_upper, state_upper)
    
    return f"""Please check for any active weather alerts in {state_name} ({state_upper}).

Use the get_alerts tool with state code: {state_upper}

After getting the alerts:
1. If there are alerts, summarize each one with severity level
2. If no alerts, confirm the state is clear
3. Provide any safety recommendations if severe weather is present"""


@mcp.prompt()
def travel_weather_check(origin_city: str, destination_city: str) -> str:
    """Check weather for a trip between two cities.
    
    Args:
        origin_city: Starting city name
        destination_city: Destination city name
    """
    origin_data = EXAMPLE_CITIES.get(origin_city)
    dest_data = EXAMPLE_CITIES.get(destination_city)
    
    prompt_parts = [f"I'm planning a trip from {origin_city} to {destination_city}. Please help me check the weather for both locations.\n"]
    
    if origin_data:
        prompt_parts.append(f"Origin ({origin_city}): lat={origin_data['lat']}, lon={origin_data['lon']}, state={origin_data['state']}")
    else:
        prompt_parts.append(f"Origin ({origin_city}): coordinates not pre-loaded, may need to look up")
    
    if dest_data:
        prompt_parts.append(f"Destination ({destination_city}): lat={dest_data['lat']}, lon={dest_data['lon']}, state={dest_data['state']}")
    else:
        prompt_parts.append(f"Destination ({destination_city}): coordinates not pre-loaded, may need to look up")
    
    prompt_parts.append("""
Please:
1. Get the forecast for both cities (use get_forecast for each)
2. Check for weather alerts in both states (use get_alerts)
3. Compare the weather conditions
4. Provide travel recommendations based on the weather""")
    
    return "\n".join(prompt_parts)


@mcp.prompt()
def weekly_planning(city: str) -> str:
    """Get a detailed weather summary for weekly planning.
    
    Args:
        city: City name for the weather forecast
    """
    city_data = EXAMPLE_CITIES.get(city)
    
    if city_data:
        return f"""I need to plan my week in {city}. Please provide a comprehensive weather overview.

Use get_forecast with coordinates: lat={city_data['lat']}, lon={city_data['lon']}
Also check get_alerts for state: {city_data['state']}

Please provide:
1. Day-by-day breakdown of expected weather
2. Best days for outdoor activities
3. Any days to avoid being outside
4. Clothing/preparation recommendations
5. Any active weather alerts to be aware of"""
    else:
        available = ", ".join(EXAMPLE_CITIES.keys())
        return f"""City "{city}" not found in quick-reference. Available: {available}

Please either select an available city or provide coordinates for {city}."""


def main():
    # Initialize and run the server
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()