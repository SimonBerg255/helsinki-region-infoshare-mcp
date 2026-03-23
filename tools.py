from __future__ import annotations

import html
import re
from datetime import datetime, timedelta
from typing import Optional, Union

import httpx

SERVICEMAP_BASE = "https://api.hel.fi/servicemap/v2"
LINKEDEVENTS_BASE = "https://api.hel.fi/linkedevents/v1"
STATISTICS_BASE = "https://stat.hel.fi/api/v1"

VALID_MUNICIPALITIES = ["helsinki", "espoo", "vantaa", "kauniainen"]
VALID_LANGS = ["fi", "sv", "en"]

HTTP_TIMEOUT = 20.0


def _localized(obj: dict | str | None, lang: str) -> str:
    if obj is None:
        return ""
    if isinstance(obj, str):
        return obj
    return obj.get(lang) or obj.get("fi") or obj.get("en") or obj.get("sv") or ""


def _strip_html(text: str) -> str:
    text = re.sub(r"<br\s*/?>", "\n", text)
    text = re.sub(r"<[^>]+>", "", text)
    text = html.unescape(text)
    return text.strip()


# --- COMMON SERVICE TYPE MAPPINGS ---
# Pre-mapped IDs for the most commonly asked service types.
# Users can also use list_service_categories to discover more.
COMMON_SERVICES = {
    "library": 813,
    "health centre": 703,
    "health center": 703,
    "health station": 703,
    "daycare": 869,
    "kindergarten": 869,
    "school": 250,
    "comprehensive school": 250,
    "swimming pool": 617,
    "swimming hall": 617,
    "playground": 648,
    "sports field": 632,
    "park": 55,
    "recycling": 359,
    "youth centre": 538,
    "youth center": 538,
    "maternity clinic": 204,
}


async def search_services(
    service_type: str,
    municipality: str = "",
    lang: str = "en",
    page_size: int = 10,
) -> dict:
    """
    Search for public services and facilities in the Helsinki metropolitan area (Helsinki, Espoo, Vantaa, Kauniainen).

    Use this tool when the user asks about locations of city services like libraries, schools, health centres, daycare, swimming pools, playgrounds, parks, youth centres, recycling points, etc.

    Args:
        service_type: Type of service to search for. Use common names like "library", "health centre", "daycare", "school", "swimming pool", "playground", "park", "recycling", "youth centre". You can also provide a numeric service ID.
        municipality: Filter by municipality. One of: helsinki, espoo, vantaa, kauniainen. Leave empty for all municipalities.
        lang: Language for results. One of: fi, sv, en. Default: en.
        page_size: Number of results to return (1-20). Default: 10.

    Returns:
        Dictionary with count of total matches and a list of service units with name, address, municipality, phone, and website.
    """
    lang = lang if lang in VALID_LANGS else "en"
    page_size = max(1, min(20, page_size))

    # Resolve service type to numeric ID
    service_id = None
    service_type_lower = service_type.strip().lower()

    if service_type_lower.isdigit():
        service_id = int(service_type_lower)
    elif service_type_lower in COMMON_SERVICES:
        service_id = COMMON_SERVICES[service_type_lower]

    params = {
        "format": "json",
        "page_size": page_size,
        "only": "name,street_address,municipality,phone,www,location,accessibility_shortcoming_count",
    }

    if service_id:
        params["service"] = service_id

    if municipality:
        muni = municipality.strip().lower()
        if muni in VALID_MUNICIPALITIES:
            params["municipality"] = muni

    # If no service ID resolved, fall back to search endpoint
    if not service_id:
        params_search = {
            "format": "json",
            "q": service_type,
            "page_size": page_size,
            "type": "unit",
        }
        if municipality:
            muni = municipality.strip().lower()
            if muni in VALID_MUNICIPALITIES:
                params_search["municipality"] = muni

        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
            resp = await client.get(f"{SERVICEMAP_BASE}/search/", params=params_search)
            resp.raise_for_status()
            data = resp.json()

        results = data.get("results", [])
        units = []
        for u in results[:page_size]:
            obj = u.get("object", u)
            units.append(_format_unit(obj, lang))

        return {
            "total_count": data.get("count", len(results)),
            "returned": len(units),
            "units": units,
        }

    async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
        resp = await client.get(f"{SERVICEMAP_BASE}/unit/", params=params)
        resp.raise_for_status()
        data = resp.json()

    results = data.get("results", [])
    units = [_format_unit(u, lang) for u in results]

    return {
        "total_count": data.get("count", 0),
        "returned": len(units),
        "units": units,
    }


def _format_unit(u: dict, lang: str) -> dict:
    loc = u.get("location", {})
    coords = loc.get("coordinates", [None, None]) if loc else [None, None]
    return {
        "id": u.get("id"),
        "name": _localized(u.get("name"), lang),
        "street_address": _localized(u.get("street_address"), lang),
        "municipality": u.get("municipality", ""),
        "phone": u.get("phone") or "",
        "website": _localized(u.get("www"), lang),
        "latitude": coords[1] if coords and len(coords) > 1 else None,
        "longitude": coords[0] if coords and len(coords) > 0 else None,
    }


async def get_service_details(unit_id: int, lang: str = "en") -> dict:
    """
    Get detailed information about a specific service unit (facility/location) by its ID.

    Use this tool when the user wants more details about a specific service unit found via search_services, such as opening hours, accessibility info, or a description.

    Args:
        unit_id: The numeric ID of the service unit (from search_services results).
        lang: Language for results. One of: fi, sv, en. Default: en.

    Returns:
        Detailed information including name, address, description, phone, website, opening hours, and accessibility notes.
    """
    lang = lang if lang in VALID_LANGS else "en"

    async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
        resp = await client.get(
            f"{SERVICEMAP_BASE}/unit/{unit_id}/",
            params={"format": "json"},
        )
        resp.raise_for_status()
        u = resp.json()

    loc = u.get("location", {})
    coords = loc.get("coordinates", [None, None]) if loc else [None, None]

    # Extract opening hours from connections
    opening_hours = []
    for conn in u.get("connections", []):
        section = conn.get("section_type")
        if section in ("OPENING_HOURS", "OPENING_HOUR_OBJECT"):
            name = _localized(conn.get("name"), lang)
            www = _localized(conn.get("www"), lang)
            if name:
                opening_hours.append({"info": name, "url": www})

    # Extract other contact info from connections
    highlights = []
    for conn in u.get("connections", []):
        section = conn.get("section_type")
        if section == "HIGHLIGHT":
            name = _localized(conn.get("name"), lang)
            if name:
                highlights.append(name)

    desc = _localized(u.get("description"), lang)
    if desc:
        desc = _strip_html(desc)
        if len(desc) > 500:
            desc = desc[:500] + "..."

    # Services can be IDs (ints) or dicts depending on the API version
    services = []
    for s in u.get("services", [])[:10]:
        if isinstance(s, dict):
            sname = _localized(s.get("name"), lang)
            if sname:
                services.append(sname)
        elif isinstance(s, int):
            services.append(s)

    return {
        "id": u.get("id"),
        "name": _localized(u.get("name"), lang),
        "street_address": _localized(u.get("street_address"), lang),
        "address_zip": u.get("address_zip", ""),
        "municipality": u.get("municipality", ""),
        "phone": u.get("phone") or "",
        "email": u.get("email") or "",
        "website": _localized(u.get("www"), lang),
        "description": desc,
        "latitude": coords[1] if coords and len(coords) > 1 else None,
        "longitude": coords[0] if coords and len(coords) > 0 else None,
        "opening_hours": opening_hours[:5],
        "highlights": highlights[:5],
        "services_offered": services,
        "accessibility_shortcoming_count": u.get("accessibility_shortcoming_count"),
    }


async def list_service_categories(
    search: str = "",
    lang: str = "en",
    page_size: int = 15,
) -> dict:
    """
    Browse or search available service categories in the Helsinki metropolitan area Service Map.

    Use this tool to discover what types of services are available when the user asks about services you do not have a pre-mapped ID for. Returns service type names and their IDs that can be used with search_services.

    Args:
        search: Optional keyword to filter service categories (e.g. "health", "sport", "culture"). Leave empty to browse top-level categories.
        lang: Language for results. One of: fi, sv, en. Default: en.
        page_size: Number of results to return (1-20). Default: 15.

    Returns:
        List of service categories with their IDs, names, and unit counts.
    """
    lang = lang if lang in VALID_LANGS else "en"
    page_size = max(1, min(20, page_size))

    if search:
        # Search service nodes by keyword
        params = {
            "format": "json",
            "page_size": page_size,
            "q": search,
            "type": "service",
        }
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
            resp = await client.get(f"{SERVICEMAP_BASE}/search/", params=params)
            resp.raise_for_status()
            data = resp.json()

        results = data.get("results", [])
        categories = []
        for r in results[:page_size]:
            obj = r.get("object", r)
            categories.append({
                "id": obj.get("id"),
                "name": _localized(obj.get("name"), lang),
                "unit_count": obj.get("unit_count", {}).get("total", 0) if isinstance(obj.get("unit_count"), dict) else obj.get("unit_count", 0),
            })
        return {"total_count": data.get("count", len(results)), "categories": categories}

    # Browse top-level service nodes
    params = {
        "format": "json",
        "page_size": page_size,
        "level": 1,
    }
    async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
        resp = await client.get(f"{SERVICEMAP_BASE}/service_node/", params=params)
        resp.raise_for_status()
        data = resp.json()

    results = data.get("results", [])
    categories = []
    for node in results[:page_size]:
        categories.append({
            "id": node.get("id"),
            "name": _localized(node.get("name"), lang),
            "children_count": len(node.get("children", [])),
        })
    return {"total_count": data.get("count", len(results)), "categories": categories}


async def search_events(
    query: str = "",
    start_date: str = "",
    end_date: str = "",
    is_free: Optional[bool] = None,
    lang: str = "en",
    page_size: int = 10,
) -> dict:
    """
    Search for events happening in the Helsinki metropolitan area.

    Use this tool when the user asks about events, things to do, concerts, exhibitions, festivals, sports events, or cultural happenings in Helsinki, Espoo, Vantaa, or Kauniainen.

    Args:
        query: Free-text search keyword (e.g. "music", "art", "children", "theatre"). Leave empty for all events.
        start_date: Start date filter in YYYY-MM-DD format. Defaults to today.
        end_date: End date filter in YYYY-MM-DD format. Leave empty for open-ended.
        is_free: If True, only show free events. If False, show all events. Default: None (all events).
        lang: Language for results. One of: fi, sv, en. Default: en.
        page_size: Number of results to return (1-15). Default: 10.

    Returns:
        Dictionary with total count and list of events with name, description, dates, location, price info, and URL.
    """
    lang = lang if lang in VALID_LANGS else "en"
    page_size = max(1, min(15, page_size))

    if not start_date:
        start_date = "today"

    params = {
        "format": "json",
        "page_size": page_size,
        "start": start_date,
        "include": "location",
        "sort": "start_time",
        "super_event_type": "none",
    }

    if query:
        params["text"] = query
    if end_date:
        params["end"] = end_date
    if is_free is True:
        params["is_free"] = "true"

    async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
        resp = await client.get(f"{LINKEDEVENTS_BASE}/event/", params=params)
        resp.raise_for_status()
        data = resp.json()

    meta = data.get("meta", {})
    results = data.get("data", [])

    events = []
    for e in results[:page_size]:
        # Location info
        location = e.get("location", {}) or {}
        loc_name = _localized(location.get("name"), lang) if location else ""
        loc_addr = ""
        if location and location.get("street_address"):
            loc_addr = _localized(location.get("street_address"), lang)

        # Description
        desc = _localized(e.get("short_description"), lang)
        if not desc:
            desc = _localized(e.get("description"), lang)
        if desc:
            desc = _strip_html(desc)
            if len(desc) > 300:
                desc = desc[:300] + "..."

        # Price info
        offers = e.get("offers", [])
        price_info = ""
        if e.get("is_free"):
            price_info = "Free"
        elif offers:
            price_str = _localized(offers[0].get("price"), lang)
            info_str = _localized(offers[0].get("info_url"), lang)
            price_info = price_str or info_str or ""

        # Dates
        start = e.get("start_time", "")
        end = e.get("end_time", "")

        event_url = ""
        info_links = e.get("info_url", {})
        if info_links:
            event_url = _localized(info_links, lang)

        events.append({
            "id": e.get("id", ""),
            "name": _localized(e.get("name"), lang),
            "description": desc,
            "start_time": start,
            "end_time": end,
            "location_name": loc_name,
            "location_address": loc_addr,
            "price": price_info,
            "event_url": event_url,
        })

    return {
        "total_count": meta.get("count", len(results)),
        "returned": len(events),
        "events": events,
    }


async def count_services(
    service_type: str,
    lang: str = "en",
) -> dict:
    """
    Count the number of a specific service type across all Helsinki metropolitan area municipalities.

    Use this tool when the user asks "how many" of a service type exist, or wants a comparison across municipalities. For example: "How many libraries are there in each municipality?" or "How many daycare centres in Helsinki?"

    Args:
        service_type: Type of service to count. Use common names like "library", "health centre", "daycare", "school", "swimming pool", "playground", "park".
        lang: Language for results. One of: fi, sv, en. Default: en.

    Returns:
        Dictionary with total count and count per municipality.
    """
    lang = lang if lang in VALID_LANGS else "en"

    service_type_lower = service_type.strip().lower()
    service_id = None
    if service_type_lower.isdigit():
        service_id = int(service_type_lower)
    elif service_type_lower in COMMON_SERVICES:
        service_id = COMMON_SERVICES[service_type_lower]

    if not service_id:
        return {
            "error": f"Unknown service type: '{service_type}'. Use list_service_categories to find the correct service type ID.",
            "known_types": list(COMMON_SERVICES.keys()),
        }

    counts = {}
    total = 0

    async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
        for muni in VALID_MUNICIPALITIES:
            resp = await client.get(
                f"{SERVICEMAP_BASE}/unit/",
                params={
                    "format": "json",
                    "service": service_id,
                    "municipality": muni,
                    "page_size": 1,
                    "only": "id",
                },
            )
            resp.raise_for_status()
            data = resp.json()
            count = data.get("count", 0)
            counts[muni.capitalize()] = count
            total += count

    return {
        "service_type": service_type,
        "service_id": service_id,
        "total": total,
        "by_municipality": counts,
    }


# --- POPULATION STATISTICS ---

# Pre-mapped area codes for PxWeb API
AREA_CODES = {
    "helsinki": "0910000000",
    "espoo": "0490000000",
    "vantaa": "0920000000",
    "kauniainen": "2350000000",
}

POPULATION_TABLE_PATH = "fi/Aluesarjat/vrm/vaerak/alu_vaerak_004r.px"


async def get_population_statistics(
    municipality: str = "",
    start_year: int = 2015,
    end_year: int = 2024,
) -> dict:
    """
    Get population statistics for Helsinki metropolitan area municipalities.

    Use this tool when the user asks about population numbers, population growth, or demographic trends for Helsinki, Espoo, Vantaa, or Kauniainen.

    Note: Statistics data labels are in Finnish. The tool translates municipality names but some category labels may remain in Finnish.

    Args:
        municipality: Municipality name (helsinki, espoo, vantaa, kauniainen). Leave empty for all four municipalities.
        start_year: Start year for data range (2000-2024). Default: 2015.
        end_year: End year for data range (2000-2024). Default: 2024.

    Returns:
        Population figures by municipality and year.
    """
    start_year = max(2000, min(2024, start_year))
    end_year = max(start_year, min(2024, end_year))
    years = [str(y) for y in range(start_year, end_year + 1)]

    if municipality:
        muni = municipality.strip().lower()
        if muni not in AREA_CODES:
            return {"error": f"Unknown municipality: '{municipality}'. Valid options: helsinki, espoo, vantaa, kauniainen"}
        areas = {muni: AREA_CODES[muni]}
    else:
        areas = AREA_CODES

    query_body = {
        "query": [
            {
                "code": "Osa-alue",
                "selection": {
                    "filter": "item",
                    "values": list(areas.values()),
                },
            },
            {
                "code": "Ikä",
                "selection": {
                    "filter": "item",
                    "values": ["ALL"],
                },
            },
            {
                "code": "Vuosi",
                "selection": {
                    "filter": "item",
                    "values": years,
                },
            },
        ],
        "response": {"format": "json"},
    }

    async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
        resp = await client.post(
            f"{STATISTICS_BASE}/{POPULATION_TABLE_PATH}",
            json=query_body,
        )
        resp.raise_for_status()
        data = resp.json()

    # Parse PxWeb JSON-stat response
    columns = data.get("columns", [])
    raw_data = data.get("data", [])

    # Reverse lookup: code -> municipality name
    code_to_name = {v: k.capitalize() for k, v in areas.items()}

    results = {}
    for row in raw_data:
        keys = row.get("key", [])
        values = row.get("values", [])

        # Keys are: [area_code, age_group, year]
        if len(keys) >= 3 and len(values) >= 1:
            area_code = keys[0]
            year = keys[2]
            population = values[0]

            muni_name = code_to_name.get(area_code, area_code)
            if muni_name not in results:
                results[muni_name] = {}
            try:
                results[muni_name][year] = int(population)
            except (ValueError, TypeError):
                results[muni_name][year] = population

    return {
        "data_source": "stat.hel.fi (Aluesarjat)",
        "metric": "Total population",
        "years": f"{start_year}-{end_year}",
        "population": results,
    }
