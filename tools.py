from __future__ import annotations

import html
import re
from typing import Optional

import httpx

SERVICEMAP_BASE = "https://api.hel.fi/servicemap/v2"
LINKEDEVENTS_BASE = "https://api.hel.fi/linkedevents/v1"
STATISTICS_BASE = "https://stat.hel.fi/api/v1"
HRI_CKAN_BASE = "https://hri.fi/data/api/3/action"

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


# =====================================================================
# SERVICE MAP TOOLS
# =====================================================================

COMMON_SERVICES = {
    "library": 813,
    "health centre": 703, "health center": 703, "health station": 703,
    "swimming pool": 729, "swimming hall": 729, "indoor pool": 729,
    "outdoor pool": 426, "open-air pool": 426, "beach": 731,
    "playground": 648, "sports field": 632, "park": 55,
    "recycling": 359, "youth centre": 538, "youth center": 538,
    "maternity clinic": 463, "child health clinic": 379,
    # Schools: use Finnish basic education grades 1-6 + 7-9 as the broadest match
    "school": 661, "primary school": 661, "elementary school": 661,
    "upper school": 662, "secondary school": 662,
    "comprehensive school": 661,
    # Daycare / early childhood — service_node approach may be better; 869 only covers Helsinki
    "daycare": 869, "kindergarten": 869,
    "pre-primary education": 159,
    # Upper secondary
    "high school": 658, "upper secondary": 658, "lukio": 658,
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

    if not service_id:
        params_search = {
            "format": "json", "q": service_type, "page_size": page_size, "type": "unit",
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
        units = [_format_unit(u.get("object", u), lang) for u in results[:page_size]]
        return {"total_count": data.get("count", len(results)), "returned": len(units), "units": units}

    async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
        resp = await client.get(f"{SERVICEMAP_BASE}/unit/", params=params)
        resp.raise_for_status()
        data = resp.json()
    results = data.get("results", [])
    units = [_format_unit(u, lang) for u in results]
    return {"total_count": data.get("count", 0), "returned": len(units), "units": units}


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
        resp = await client.get(f"{SERVICEMAP_BASE}/unit/{unit_id}/", params={"format": "json"})
        resp.raise_for_status()
        u = resp.json()

    loc = u.get("location", {})
    coords = loc.get("coordinates", [None, None]) if loc else [None, None]

    opening_hours = []
    highlights = []
    for conn in u.get("connections", []):
        section = conn.get("section_type")
        if section in ("OPENING_HOURS", "OPENING_HOUR_OBJECT"):
            name = _localized(conn.get("name"), lang)
            if name:
                opening_hours.append({"info": name, "url": _localized(conn.get("www"), lang)})
        elif section == "HIGHLIGHT":
            name = _localized(conn.get("name"), lang)
            if name:
                highlights.append(name)

    desc = _localized(u.get("description"), lang)
    if desc:
        desc = _strip_html(desc)
        if len(desc) > 500:
            desc = desc[:500] + "..."

    services = []
    for s in u.get("services", [])[:10]:
        if isinstance(s, dict):
            sname = _localized(s.get("name"), lang)
            if sname:
                services.append(sname)
        elif isinstance(s, int):
            services.append(s)

    return {
        "id": u.get("id"), "name": _localized(u.get("name"), lang),
        "street_address": _localized(u.get("street_address"), lang),
        "address_zip": u.get("address_zip", ""), "municipality": u.get("municipality", ""),
        "phone": u.get("phone") or "", "email": u.get("email") or "",
        "website": _localized(u.get("www"), lang), "description": desc,
        "latitude": coords[1] if coords and len(coords) > 1 else None,
        "longitude": coords[0] if coords and len(coords) > 0 else None,
        "opening_hours": opening_hours[:5], "highlights": highlights[:5],
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
        params = {"format": "json", "page_size": page_size, "q": search, "type": "service"}
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
            resp = await client.get(f"{SERVICEMAP_BASE}/search/", params=params)
            resp.raise_for_status()
            data = resp.json()
        results = data.get("results", [])
        categories = []
        for r in results[:page_size]:
            obj = r.get("object", r)
            uc = obj.get("unit_count", 0)
            categories.append({
                "id": obj.get("id"),
                "name": _localized(obj.get("name"), lang),
                "unit_count": uc.get("total", 0) if isinstance(uc, dict) else uc,
            })
        return {"total_count": data.get("count", len(results)), "categories": categories}

    params = {"format": "json", "page_size": page_size, "level": 1}
    async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
        resp = await client.get(f"{SERVICEMAP_BASE}/service_node/", params=params)
        resp.raise_for_status()
        data = resp.json()
    results = data.get("results", [])
    categories = [{"id": n.get("id"), "name": _localized(n.get("name"), lang), "children_count": len(n.get("children", []))} for n in results[:page_size]]
    return {"total_count": data.get("count", len(results)), "categories": categories}


async def count_services(service_type: str, lang: str = "en") -> dict:
    """
    Count the number of a specific service type across all Helsinki metropolitan area municipalities.

    Use this tool when the user asks "how many" of a service type exist, or wants a comparison across municipalities.

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
        return {"error": f"Unknown service type: '{service_type}'. Use list_service_categories to find the correct service type ID.", "known_types": list(COMMON_SERVICES.keys())}

    counts = {}
    total = 0
    async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
        for muni in VALID_MUNICIPALITIES:
            resp = await client.get(f"{SERVICEMAP_BASE}/unit/", params={"format": "json", "service": service_id, "municipality": muni, "page_size": 1, "only": "id"})
            resp.raise_for_status()
            data = resp.json()
            count = data.get("count", 0)
            counts[muni.capitalize()] = count
            total += count
    return {"service_type": service_type, "service_id": service_id, "total": total, "by_municipality": counts}


# =====================================================================
# EVENTS TOOL
# =====================================================================

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

    params = {"format": "json", "page_size": page_size, "start": start_date, "include": "location", "sort": "start_time", "super_event_type": "none"}
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
        location = e.get("location", {}) or {}
        loc_name = _localized(location.get("name"), lang) if location else ""
        loc_addr = _localized(location.get("street_address"), lang) if location and location.get("street_address") else ""

        desc = _localized(e.get("short_description"), lang) or _localized(e.get("description"), lang)
        if desc:
            desc = _strip_html(desc)
            if len(desc) > 300:
                desc = desc[:300] + "..."

        price_info = "Free" if e.get("is_free") else ""
        if not price_info and e.get("offers"):
            price_info = _localized(e["offers"][0].get("price"), lang) or ""

        event_url = _localized(e.get("info_url", {}), lang) if e.get("info_url") else ""

        events.append({
            "id": e.get("id", ""), "name": _localized(e.get("name"), lang),
            "description": desc, "start_time": e.get("start_time", ""),
            "end_time": e.get("end_time", ""), "location_name": loc_name,
            "location_address": loc_addr, "price": price_info, "event_url": event_url,
        })
    return {"total_count": meta.get("count", len(results)), "returned": len(events), "events": events}


# =====================================================================
# PXWEB STATISTICS TOOLS (stat.hel.fi — 297+ tables)
# =====================================================================

# Database descriptions for the LLM
PXWEB_DATABASES = {
    "Aluesarjat": "Regional statistics: population, housing, construction, income, labour, education for Helsinki metro sub-areas",
    "Hyvinvointitilastot": "Wellbeing statistics: children/youth/elderly welfare, health, safety, education outcomes",
    "Nordstat": "Nordic capital city comparisons (Helsinki, Stockholm, Copenhagen, Oslo) — available in English",
    "SDG": "Helsinki sustainable development indicators",
    "Ymparistotilasto": "Environmental statistics: energy, emissions, traffic, nature, water, waste, land use",
}


async def browse_statistics(
    path: str = "",
    lang: str = "fi",
) -> dict:
    """
    Browse the Helsinki region statistical database tree (stat.hel.fi PxWeb API). Contains ~297 tables across 5 databases covering population, housing, labour, environment, wellbeing, and more.

    Use this tool to explore what statistical data is available. Start with an empty path to see top-level databases, then drill into categories.

    IMPORTANT: Most data is only available in Finnish (lang=fi). Only Nordstat has English translations.

    Args:
        path: Path to browse. Examples:
            - "" (empty) = list all databases
            - "Aluesarjat" = list categories in regional statistics
            - "Aluesarjat/vrm" = list population subcategories
            - "Aluesarjat/vrm/vaerak" = list population structure tables
            - "Ymparistotilasto" = list environmental categories
            - "Nordstat" = Nordic city comparisons (English available)
        lang: Language. Use "fi" (Finnish, most complete) or "en" (English, limited to Nordstat). Default: fi.

    Returns:
        List of items at that path — either folders (type=l) to browse deeper, or tables (type=t) to query with query_statistics.
    """
    lang = lang if lang in ["fi", "en", "sv"] else "fi"

    if not path:
        return {
            "databases": [
                {"id": db_id, "description": desc}
                for db_id, desc in PXWEB_DATABASES.items()
            ],
            "hint": "Pass a database name as 'path' to browse its categories. Example: path='Aluesarjat'",
        }

    url = f"{STATISTICS_BASE}/{lang}/{path}/"
    async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
        resp = await client.get(url)
        if resp.status_code == 400:
            # English not available for this path, try Finnish
            if lang != "fi":
                resp = await client.get(f"{STATISTICS_BASE}/fi/{path}/")
                resp.raise_for_status()
                items = resp.json()
                return {"path": path, "lang_fallback": "fi", "note": "English not available for this path, showing Finnish", "items": [{"id": i["id"], "text": i["text"], "type": "folder" if i["type"] == "l" else "table"} for i in items[:30]]}
            resp.raise_for_status()
        resp.raise_for_status()
        items = resp.json()

    return {
        "path": path,
        "items": [
            {"id": i["id"], "text": i["text"].strip(), "type": "folder" if i["type"] == "l" else "table"}
            for i in items[:30]
        ],
        "hint": "For folders, append the id to the path. For tables, use get_table_info to see variables, then query_statistics to fetch data.",
    }


async def get_table_info(
    table_path: str,
    lang: str = "fi",
) -> dict:
    """
    Get metadata (variables, dimensions, value options) for a specific PxWeb statistics table. Use this before query_statistics to understand what filters are available.

    Args:
        table_path: Full path to the table including the .px filename. Examples:
            - "Aluesarjat/vrm/vaerak/alu_vaerak_004r.px" (population by age and area)
            - "Aluesarjat/tyo/tyom/alu_tyom_003u.px" (monthly unemployment)
            - "Aluesarjat/asu/askan/alu_askan_005q.px" (housing stock)
            - "Ymparistotilasto/ilmas/kaspa/ymp_kaspa_003k.px" (greenhouse gas emissions)
            - "Nordstat/popu/nor_popu_001a.px" (Nordic cities population)
        lang: Language (fi or en). Default: fi.

    Returns:
        Table title and list of variables with their codes and available values (first 20 values shown per variable).
    """
    lang = lang if lang in ["fi", "en", "sv"] else "fi"
    url = f"{STATISTICS_BASE}/{lang}/{table_path}"

    async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
        resp = await client.get(url)
        if resp.status_code == 400 and lang != "fi":
            resp = await client.get(f"{STATISTICS_BASE}/fi/{table_path}")
        resp.raise_for_status()
        data = resp.json()

    title = data.get("title", "")
    variables = []
    for var in data.get("variables", []):
        vals = var.get("values", [])
        texts = var.get("valueTexts", [])
        paired = list(zip(vals[:20], texts[:20]))
        variables.append({
            "code": var.get("code"),
            "text": var.get("text"),
            "total_values": len(vals),
            "values_sample": paired,
            "hint": f"...and {len(vals) - 20} more" if len(vals) > 20 else None,
        })

    return {
        "table_path": table_path,
        "title": title,
        "variables": variables,
        "hint": "Use query_statistics with this table_path and provide filters for each variable code.",
    }


async def query_statistics(
    table_path: str,
    filters: dict,
    lang: str = "fi",
    max_rows: int = 50,
) -> dict:
    """
    Query data from any PxWeb statistics table on stat.hel.fi. First use browse_statistics to find tables and get_table_info to see available variables and values.

    Args:
        table_path: Full path to the .px table. Example: "Aluesarjat/vrm/vaerak/alu_vaerak_004r.px"
        filters: Dictionary mapping variable codes to lists of values. Example:
            {"Osa-alue": ["0910000000", "0490000000"], "Ikä": ["ALL"], "Vuosi": ["2023", "2024"]}
            Get variable codes and valid values from get_table_info.
            IMPORTANT: You must include a filter for every variable in the table, or the query may return too much data.
        lang: Language (fi or en). Default: fi.
        max_rows: Maximum data rows to return (1-100). Default: 50. Limits response size for the LLM.

    Returns:
        Column definitions and data rows from the statistical table.
    """
    lang = lang if lang in ["fi", "en", "sv"] else "fi"
    max_rows = max(1, min(100, max_rows))

    query_items = []
    for code, values in filters.items():
        query_items.append({
            "code": code,
            "selection": {"filter": "item", "values": values},
        })

    query_body = {"query": query_items, "response": {"format": "json"}}

    url = f"{STATISTICS_BASE}/{lang}/{table_path}"
    async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
        resp = await client.post(url, json=query_body)
        if resp.status_code == 400 and lang != "fi":
            resp = await client.post(f"{STATISTICS_BASE}/fi/{table_path}", json=query_body)
        resp.raise_for_status()
        data = resp.json()

    columns = [{"code": c.get("code"), "text": c.get("text"), "type": c.get("type")} for c in data.get("columns", [])]
    raw_rows = data.get("data", [])
    total_rows = len(raw_rows)
    rows = []
    for row in raw_rows[:max_rows]:
        rows.append({"keys": row.get("key", []), "values": row.get("values", [])})

    return {
        "table_path": table_path,
        "columns": columns,
        "total_rows": total_rows,
        "returned_rows": len(rows),
        "data": rows,
        "truncated": total_rows > max_rows,
    }


# =====================================================================
# PRE-BUILT HIGH-VALUE STATISTICS TOOLS
# =====================================================================

AREA_CODES = {
    "helsinki": "0910000000", "espoo": "0490000000",
    "vantaa": "0920000000", "kauniainen": "2350000000",
}


async def get_population_statistics(
    municipality: str = "",
    start_year: int = 2015,
    end_year: int = 2024,
) -> dict:
    """
    Get population statistics for Helsinki metropolitan area municipalities.

    Use this tool when the user asks about population numbers, population growth, or demographic trends for Helsinki, Espoo, Vantaa, or Kauniainen.

    Note: Statistics data labels are in Finnish. The tool translates municipality names.

    Args:
        municipality: Municipality name (helsinki, espoo, vantaa, kauniainen). Leave empty for all four municipalities.
        start_year: Start year for data range (1974-2024). Default: 2015.
        end_year: End year for data range (1974-2024). Default: 2024.

    Returns:
        Population figures by municipality and year.
    """
    start_year = max(1974, min(2024, start_year))
    end_year = max(start_year, min(2024, end_year))
    years = [str(y) for y in range(start_year, end_year + 1)]

    if municipality:
        muni = municipality.strip().lower()
        if muni not in AREA_CODES:
            return {"error": f"Unknown municipality: '{municipality}'. Valid: helsinki, espoo, vantaa, kauniainen"}
        areas = {muni: AREA_CODES[muni]}
    else:
        areas = AREA_CODES

    query_body = {"query": [
        {"code": "Osa-alue", "selection": {"filter": "item", "values": list(areas.values())}},
        {"code": "Ikä", "selection": {"filter": "item", "values": ["ALL"]}},
        {"code": "Vuosi", "selection": {"filter": "item", "values": years}},
    ], "response": {"format": "json"}}

    async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
        resp = await client.post(f"{STATISTICS_BASE}/fi/Aluesarjat/vrm/vaerak/alu_vaerak_004r.px", json=query_body)
        resp.raise_for_status()
        data = resp.json()

    code_to_name = {v: k.capitalize() for k, v in areas.items()}
    results = {}
    for row in data.get("data", []):
        keys = row.get("key", [])
        values = row.get("values", [])
        if len(keys) >= 3 and values:
            muni_name = code_to_name.get(keys[0], keys[0])
            if muni_name not in results:
                results[muni_name] = {}
            try:
                results[muni_name][keys[2]] = int(values[0])
            except (ValueError, TypeError):
                results[muni_name][keys[2]] = values[0]

    return {"data_source": "stat.hel.fi (Aluesarjat)", "metric": "Total population (31 Dec)", "years": f"{start_year}-{end_year}", "population": results}


async def get_unemployment_data(
    months: str = "",
    municipality: str = "",
) -> dict:
    """
    Get monthly unemployment data for Helsinki metropolitan area municipalities.

    Use this tool when the user asks about unemployment rates, jobseekers, or labour market conditions in the Helsinki region.

    Args:
        months: Comma-separated months in YYYYMNN format (e.g. "2024M01,2024M06,2024M12"). Leave empty for the last 12 months.
        municipality: Filter by municipality code: "091" (Helsinki), "049" (Espoo), "092" (Vantaa), "235" (Kauniainen), "PKS" (capital region). Leave empty for all.

    Returns:
        Unemployment rate, jobseekers count, and related indicators by area and month.
    """
    if not months:
        import datetime
        now = datetime.date.today()
        month_list = []
        for i in range(12, 0, -1):
            y = now.year
            m = now.month - i
            if m <= 0:
                m += 12
                y -= 1
            month_list.append(f"{y}M{m:02d}")
        months = ",".join(month_list)

    month_values = [m.strip() for m in months.split(",")]

    area_map = {
        "091": "Helsinki", "049": "Espoo", "092": "Vantaa",
        "235": "Kauniainen", "PKS": "Capital region",
        "Kehyskunnat": "Surrounding municipalities",
        "Helsingin_seutu": "Helsinki region", "Koko_maa": "Finland",
    }

    if municipality:
        area_values = [municipality.strip()]
    else:
        area_values = ["091", "049", "092"]

    # Key indicators: unemployment rate, unemployed jobseekers, long-term unemployed
    indicator_values = ["TYOTOSUUS", "TYOTTOMATLOPUSSA", "PITKAAIKAISTYOTTOMAT"]

    query_body = {"query": [
        {"code": "Kuukausi", "selection": {"filter": "item", "values": month_values}},
        {"code": "Alue", "selection": {"filter": "item", "values": area_values}},
        {"code": "Tiedot", "selection": {"filter": "item", "values": indicator_values}},
    ], "response": {"format": "json"}}

    async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
        resp = await client.post(f"{STATISTICS_BASE}/fi/Aluesarjat/tyo/tyom/alu_tyom_003u.px", json=query_body)
        resp.raise_for_status()
        data = resp.json()

    indicator_names = {
        "TYOTOSUUS": "Unemployment rate (%)",
        "TYOTTOMATLOPUSSA": "Unemployed jobseekers",
        "PITKAAIKAISTYOTTOMAT": "Long-term unemployed (>1 year)",
    }

    # Parse response — Tiedot values become columns, not row keys
    columns = data.get("columns", [])
    col_codes = [c.get("code") for c in columns]

    results = {}
    for row in data.get("data", []):
        keys = row.get("key", [])
        values = row.get("values", [])
        if len(keys) >= 2 and values:
            month, area = keys[0], keys[1]
            area_name = area_map.get(area, area)
            if area_name not in results:
                results[area_name] = {}
            if month not in results[area_name]:
                results[area_name][month] = {}
            # Map values to indicator column names
            for i, val in enumerate(values):
                col_idx = len(keys) + i  # columns after key columns
                if col_idx < len(col_codes):
                    ind_code = col_codes[col_idx]
                    ind_name = indicator_names.get(ind_code, ind_code)
                else:
                    ind_name = indicator_names.get(indicator_values[i], f"indicator_{i}") if i < len(indicator_values) else f"value_{i}"
                try:
                    results[area_name][month][ind_name] = float(val)
                except (ValueError, TypeError):
                    results[area_name][month][ind_name] = val

    return {"data_source": "stat.hel.fi (Aluesarjat)", "metric": "Monthly unemployment data", "results": results}


async def get_emissions_data(
    start_year: int = 2015,
    end_year: int = 2024,
) -> dict:
    """
    Get Helsinki greenhouse gas emissions data by sector.

    Use this tool when the user asks about carbon emissions, climate targets, greenhouse gases, or energy-related environmental data for Helsinki.

    Args:
        start_year: Start year (1990-2024). Default: 2015.
        end_year: End year (1990-2024). Default: 2024.

    Returns:
        Emissions in 1000t CO2-eq and per capita by sector (district heating, transport, electricity, etc.) and year.
    """
    start_year = max(1990, min(2024, start_year))
    end_year = max(start_year, min(2024, end_year))
    years = [str(y) for y in range(start_year, end_year + 1)]

    query_body = {"query": [
        {"code": "Alue", "selection": {"filter": "item", "values": ["hki"]}},
        {"code": "Sektori", "selection": {"filter": "item", "values": [
            "kaulä", "öljlä", "sählä",
            "kulsä", "liik", "teolty",
            "jätkäs", "maata", "yht",
        ]}},
        {"code": "Tiedot", "selection": {"filter": "item", "values": ["kokpää", "askoh"]}},
        {"code": "Vuosi", "selection": {"filter": "item", "values": years}},
    ], "response": {"format": "json"}}

    sector_names = {
        "kaulä": "District heating", "öljlä": "Oil heating",
        "sählä": "Electric heating", "kulsä": "Consumption electricity",
        "liik": "Transport", "teolty": "Industry & machinery",
        "jätkäs": "Waste management", "maata": "Agriculture", "yht": "Total",
    }
    metric_names = {"kokpää": "Total (1000t CO2-eq)", "askoh": "Per capita (t CO2-eq)"}

    async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
        resp = await client.post(f"{STATISTICS_BASE}/fi/Ymparistotilasto/ilmas/kaspa/ymp_kaspa_003k.px", json=query_body)
        resp.raise_for_status()
        data = resp.json()

    # Parse — keys are [area, sector, year], Tiedot values become columns
    columns = data.get("columns", [])
    col_codes = [c.get("code") for c in columns]

    results = {}
    for row in data.get("data", []):
        keys = row.get("key", [])
        values = row.get("values", [])
        if len(keys) >= 3 and values:
            _, sector, year = keys[0], keys[1], keys[2]
            sector_name = sector_names.get(sector, sector)
            if sector_name not in results:
                results[sector_name] = {}
            if year not in results[sector_name]:
                results[sector_name][year] = {}
            for i, val in enumerate(values):
                col_idx = len(keys) + i
                if col_idx < len(col_codes):
                    metric_code = col_codes[col_idx]
                    metric_label = metric_names.get(metric_code, metric_code)
                else:
                    metric_label = f"value_{i}"
                try:
                    results[sector_name][year][metric_label] = float(val)
                except (ValueError, TypeError):
                    results[sector_name][year][metric_label] = val

    return {"data_source": "stat.hel.fi (Ymparistotilasto)", "metric": "Helsinki greenhouse gas emissions", "years": f"{start_year}-{end_year}", "emissions": results}


# =====================================================================
# HRI CATALOGUE SEARCH TOOL
# =====================================================================

async def search_datasets(
    query: str = "",
    format_filter: str = "",
    category: str = "",
    page_size: int = 10,
) -> dict:
    """
    Search the Helsinki Region Infoshare (HRI) open data catalogue. Contains 550+ datasets in formats including PXWEB (117), XLSX (165), CSV (47), JSON (40), and geospatial formats.

    Use this tool when the user asks what data is available, wants to find a specific dataset, or asks about open data in the Helsinki region. Also useful for finding downloadable files (CSV, XLSX) on specific topics.

    Args:
        query: Free-text search keyword (e.g. "population", "housing", "traffic", "energy", "education"). Leave empty for browsing.
        format_filter: Filter by resource format. Options: PXWEB, CSV, XLSX, JSON, WFS, WMS, XLS, SHP, KML, XML. Leave empty for all.
        category: Filter by category slug. Options: vaesto (population), asuminen (housing), rakennettu-ymparisto (built env), ymparisto-ja-luonto (environment), liikenne-ja-matkailu (traffic), kulttuuri-ja-vapaa-aika (culture), opetus-ja-koulutus (education), talous-ja-verotus (economy), tyo-ja-elinkeinot (work), terveys-ja-sosiaalipalvelut (health), hallinto-ja-paatoksenteko (governance), kartat (maps). Leave empty for all.
        page_size: Number of results (1-20). Default: 10.

    Returns:
        List of datasets with titles, descriptions, formats, and resource URLs.
    """
    page_size = max(1, min(20, page_size))
    params = {"rows": page_size}

    fq_parts = []
    if format_filter:
        fq_parts.append(f"res_format:{format_filter.upper()}")
    if category:
        fq_parts.append(f"groups:{category}")
    if fq_parts:
        params["fq"] = " ".join(fq_parts)
    if query:
        params["q"] = query

    async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
        resp = await client.get(f"{HRI_CKAN_BASE}/package_search", params=params)
        resp.raise_for_status()
        data = resp.json()

    result_data = data.get("result", {})
    total = result_data.get("count", 0)
    datasets = []
    for pkg in result_data.get("results", [])[:page_size]:
        title_tr = pkg.get("title_translated", {})
        title = title_tr.get("en") or title_tr.get("fi") or pkg.get("title", "")
        notes_tr = pkg.get("notes_translated", {})
        desc = notes_tr.get("en") or notes_tr.get("fi") or pkg.get("notes", "")
        if desc and len(desc) > 200:
            desc = desc[:200] + "..."

        resources = []
        for r in pkg.get("resources", [])[:5]:
            resources.append({
                "format": r.get("format", ""),
                "url": r.get("url", ""),
                "name": r.get("name", ""),
            })

        groups = [g.get("name", "") for g in pkg.get("groups", [])]
        geo = pkg.get("geographical_coverage", "")

        datasets.append({
            "title": title, "description": desc,
            "formats": list(set(r["format"] for r in resources)),
            "resources": resources, "categories": groups,
            "geographical_coverage": geo,
        })

    return {"total_count": total, "returned": len(datasets), "datasets": datasets}
