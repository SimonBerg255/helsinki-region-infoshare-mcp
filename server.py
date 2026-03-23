from pathlib import Path

from fastmcp import FastMCP
from mcp.server.fastmcp import Icon
from starlette.requests import Request
from starlette.responses import PlainTextResponse, Response

from tools import (
    browse_statistics,
    count_services,
    get_emissions_data,
    get_population_statistics,
    get_service_details,
    get_table_info,
    get_unemployment_data,
    list_service_categories,
    query_statistics,
    search_datasets,
    search_events,
    search_services,
)


####### SERVER METADATA #######


LOGO_PATH = Path(__file__).parent / "Region_info.png"

INSTRUCTION_STRING = """Helsinki Region Infoshare (HRI) — Open Data Intelligence Layer for the Helsinki Metropolitan Area.
Covers 550+ datasets from Helsinki, Espoo, Vantaa, and Kauniainen.

ROUTING GUIDE — pick the right tool for the question:

1. WHERE IS / FIND ME (libraries, schools, health centres, swimming pools, playgrounds, parks, etc.)
   → search_services with a service type name and optional municipality
   → get_service_details for opening hours, description, accessibility of one unit
   → list_service_categories to discover what service types exist
   Common service types: library, health centre, swimming pool, school, daycare, playground, park, youth centre, recycling, beach

2. HOW MANY (comparing counts across municipalities)
   → count_services with a service type name

3. WHAT'S HAPPENING / EVENTS (concerts, exhibitions, festivals, free things to do)
   → search_events with keyword and/or date range; set is_free=True for free events

4. POPULATION / UNEMPLOYMENT / EMISSIONS (quick pre-built answers)
   → get_population_statistics — population by municipality and year (1974-2024)
   → get_unemployment_data — monthly unemployment rates and jobseeker counts
   → get_emissions_data — Helsinki greenhouse gas emissions by sector (1990-2024)

5. ANY OTHER STATISTICS (housing, income, labour, education, environment, wellbeing, Nordic comparisons — 297 tables)
   → Step 1: browse_statistics to navigate the database tree
   → Step 2: get_table_info to see what variables/filters a table has
   → Step 3: query_statistics to fetch data with specific filters
   Key databases: Aluesarjat (regional), Hyvinvointitilastot (wellbeing), Ymparistotilasto (environment), Nordstat (Nordic city comparisons)

6. WHAT DATA EXISTS / DISCOVERY
   → search_datasets to search the full HRI catalogue (550+ datasets)

GEOGRAPHY: Helsinki metro area only (Helsinki, Espoo, Vantaa, Kauniainen). Questions about other cities will return no results.
LANGUAGE: Use English for services and events. Use Finnish (fi) for statistics — most PxWeb data is Finnish-only. Nordstat has English.

KNOWN LIMITATIONS:
- Service categorization differs between municipalities. Daycare (service 869) is mainly Helsinki; Espoo/Vantaa may use different IDs. Use list_service_categories or search_datasets if results seem incomplete.
- Neighborhood-level proximity search is not supported. For "nearest to X" questions, search the municipality and present results with addresses.
- Statistics variable codes are in Finnish. Always use get_table_info before query_statistics to get the correct codes.
"""

VERSION = "2.0.0"
WEBSITE_URL = "https://hri.fi"


####### SERVER CONFIGURATION #######


# The logo is served at /logo.png via a custom route below.
# Set the full URL after deployment (e.g. https://your-app.up.railway.app/logo.png).
# For now, use a relative path — Intric will resolve it against the server URL.
icon = Icon(
    src="/logo.png",
)

mcp = FastMCP(
    name="Helsinki Region Infoshare",
    instructions=INSTRUCTION_STRING,
    version=VERSION,
    website_url=WEBSITE_URL,
    icons=[icon],
)


####### TOOLS — all auto-execute without user permission #######


# Service Map tools
mcp.tool(meta={"requires_permission": False})(search_services)
mcp.tool(meta={"requires_permission": False})(get_service_details)
mcp.tool(meta={"requires_permission": False})(list_service_categories)
mcp.tool(meta={"requires_permission": False})(count_services)

# Events tool
mcp.tool(meta={"requires_permission": False})(search_events)

# Pre-built statistics tools
mcp.tool(meta={"requires_permission": False})(get_population_statistics)
mcp.tool(meta={"requires_permission": False})(get_unemployment_data)
mcp.tool(meta={"requires_permission": False})(get_emissions_data)

# Generic PxWeb statistics tools (297+ tables)
mcp.tool(meta={"requires_permission": False})(browse_statistics)
mcp.tool(meta={"requires_permission": False})(get_table_info)
mcp.tool(meta={"requires_permission": False})(query_statistics)

# HRI catalogue search
mcp.tool(meta={"requires_permission": False})(search_datasets)


####### CUSTOM ROUTES #######


@mcp.custom_route("/health", methods=["GET"])
async def health_check(request: Request) -> PlainTextResponse:
    return PlainTextResponse("OK")


@mcp.custom_route("/logo.png", methods=["GET"])
async def serve_logo(request: Request) -> Response:
    if LOGO_PATH.exists():
        content = LOGO_PATH.read_bytes()
        return Response(content=content, media_type="image/png")
    return PlainTextResponse("Logo not found", status_code=404)


####### ASGI APP #######


app = mcp.http_app()
