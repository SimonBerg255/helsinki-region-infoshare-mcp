from pathlib import Path

from fastmcp import FastMCP
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

ROUTING GUIDE — pick the right tool:

1. CITY SERVICES & FACILITIES (libraries, schools, health centres, daycare, parks, pools, etc.)
   → search_services — find facilities by type and municipality
   → count_services — "how many X in each city?"
   → get_service_details — opening hours, accessibility, description for one unit
   → list_service_categories — discover service types

2. EVENTS (concerts, exhibitions, festivals, sports, what's on)
   → search_events — by keyword, date range, free/paid

3. STATISTICS — QUICK ANSWERS (pre-built, fast)
   → get_population_statistics — population by municipality and year (1974-2024)
   → get_unemployment_data — monthly unemployment rates, jobseekers
   → get_emissions_data — Helsinki greenhouse gas emissions by sector (1990-2024)

4. STATISTICS — DEEP EXPLORATION (297 tables: population, housing, construction, income, labour, education, environment, wellbeing, Nordic comparisons)
   → browse_statistics — navigate the PxWeb database tree
   → get_table_info — see what variables/filters a table has
   → query_statistics — fetch data with filters from any table

5. DATASET DISCOVERY (what open data exists?)
   → search_datasets — search the full HRI catalogue (550+ datasets in PXWEB, CSV, XLSX, JSON, GIS formats)

GEOGRAPHY: Helsinki metro area only (Helsinki, Espoo, Vantaa, Kauniainen).
LANGUAGE: Default to Finnish (fi) for statistics. English available for services, events, and Nordstat.

WORKFLOW FOR STATISTICS QUESTIONS:
1. If it's about population, unemployment, or emissions → use the pre-built tool directly
2. For anything else → browse_statistics to find the right table → get_table_info to see variables → query_statistics to fetch data
3. If unsure what exists → search_datasets to search the catalogue
"""

VERSION = "2.0.0"
WEBSITE_URL = "https://hri.fi"


####### SERVER CONFIGURATION #######


mcp = FastMCP(
    name="Helsinki Region Infoshare",
    instructions=INSTRUCTION_STRING,
    version=VERSION,
    website_url=WEBSITE_URL,
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
