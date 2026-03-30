# Helsinki Region Infoshare MCP

An MCP server that exposes Helsinki Region Infoshare (HRI) open data as structured tools for AI assistants. It wraps four public APIs — the Helsinki Service Map (19,000+ public facilities), the Linked Events calendar (377,000+ events), the stat.hel.fi PxWeb statistics database (297 tables covering population, environment, housing, labour, and more), and the HRI CKAN dataset catalogue (550+ open datasets) — giving an AI a single interface for questions about city services, local events, and regional statistics across Helsinki, Espoo, Vantaa, and Kauniainen.

## Tools

| Tool | Description |
|------|-------------|
| `search_services` | Find public facilities (libraries, schools, health centres, pools, parks, etc.) by type and municipality |
| `get_service_details` | Get opening hours, description, accessibility info, and contact details for a specific facility |
| `list_service_categories` | Browse or search available service types to find the right category name or ID |
| `count_services` | Count a service type across all four municipalities and compare totals |
| `search_events` | Search upcoming events by keyword, date range, and free/paid filter |
| `get_population_statistics` | Population figures by municipality and year (1974–2024) |
| `get_unemployment_data` | Monthly unemployment rate, jobseeker count, and long-term unemployment by area |
| `get_emissions_data` | Helsinki greenhouse gas emissions by sector (district heating, transport, etc.) from 1990 |
| `browse_statistics` | Navigate the stat.hel.fi database tree to find statistical tables |
| `get_table_info` | Inspect a table's variables, dimension codes, and available filter values before querying |
| `query_statistics` | Fetch data from any PxWeb table with specific filters |
| `search_datasets` | Search the full HRI CKAN catalogue for datasets by keyword, format, or category |

## How it works

1. **Services and facilities** — call `search_services` with a type name (e.g. "library", "health centre") and optional municipality. Follow up with `get_service_details` on a unit ID for full contact and hours information.
2. **Events** — call `search_events` with a keyword or date range. Set `is_free=True` to filter to free events.
3. **Common statistics** — call `get_population_statistics`, `get_unemployment_data`, or `get_emissions_data` directly for the most frequently needed figures.
4. **Any other statistic** — call `browse_statistics` to navigate the database tree, then `get_table_info` on the table path to read variable codes, then `query_statistics` with those codes to fetch data.
5. **Dataset discovery** — call `search_datasets` to find what raw data HRI publishes on a topic.

## Quick start

```bash
git clone https://github.com/SimonBerg255/helsinki-region-infoshare-mcp.git
cd helsinki-region-infoshare-mcp
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
uvicorn server:app --host 0.0.0.0 --port 8000
```

## API details

- **Service Map** — `https://api.hel.fi/servicemap/v2/` — JSON REST, no auth, no rate limit documented
- **Linked Events** — `https://api.hel.fi/linkedevents/v1/` — JSON REST, no auth
- **Statistics** — `https://stat.hel.fi/api/v1/` — PxWeb JSON API, no auth; GET for metadata, POST for data
- **HRI catalogue** — `https://hri.fi/data/api/3/action/` — CKAN JSON API, no auth
- **Response format** — all tools return structured dicts; all responses are capped to prevent context overflow
- **License** — data from HRI is published under [Creative Commons Attribution 4.0](https://creativecommons.org/licenses/by/4.0/)

## Reference

**Municipalities and area codes**

| Municipality | Short code | PxWeb area code |
|---|---|---|
| Helsinki | 091 | 0910000000 |
| Espoo | 049 | 0490000000 |
| Vantaa | 092 | 0920000000 |
| Kauniainen | 235 | 2350000000 |

Use short codes (e.g. `"091"`) for `get_unemployment_data`. Use 10-character codes for `query_statistics` against Aluesarjat tables.

**Statistics databases**

| Database | Content |
|---|---|
| Aluesarjat | Regional statistics: population, housing, labour, income, education for metro sub-areas |
| Hyvinvointitilastot | Wellbeing: children, elderly, health, safety, education outcomes |
| Ymparistotilasto | Environment: energy, emissions, traffic, nature, water, waste |
| Nordstat | Nordic capital city comparisons — available in English |
| SDG | Helsinki sustainable development indicators |

**Service type names** (for `search_services` and `count_services`)

`library`, `health centre`, `health station`, `swimming pool`, `indoor pool`, `outdoor pool`, `beach`, `playground`, `sports field`, `park`, `recycling`, `youth centre`, `maternity clinic`, `child health clinic`, `school`, `primary school`, `upper school`, `daycare`, `kindergarten`, `pre-primary education`, `high school`

Pass a numeric ID directly if you need a type not in this list (use `list_service_categories` to find IDs).

**PxWeb filter syntax**

Filters are passed as a dict mapping variable codes to lists of values: `{"Osa-alue": ["0910000000"], "Vuosi": ["2023", "2024"]}`. Variable codes and valid values are returned by `get_table_info`. Variable codes may contain Finnish characters (ä, ö, å) — copy them exactly from the metadata response.

## Validation

```bash
python3 test_tools.py
```

Runs 16 live tests covering all 12 tools, including response size checks (all responses must be under 20 KB). Exits 0 on success.

## License

MIT
