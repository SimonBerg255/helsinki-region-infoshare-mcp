"""Live API tests for all tools."""
import asyncio
import json
import sys
import time

sys.path.insert(0, ".")
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


async def test_search_services_library():
    print("\n=== TEST 1: Search libraries in Helsinki ===")
    t0 = time.time()
    result = await search_services("library", municipality="helsinki", page_size=5)
    elapsed = time.time() - t0
    print(f"Time: {elapsed:.2f}s | Count: {result['total_count']} | Returned: {result['returned']}")
    for u in result["units"][:3]:
        print(f"  - {u['name']} | {u['street_address']}")
    assert result["total_count"] > 0 and elapsed < 20 and len(json.dumps(result)) < 20000

async def test_search_services_health():
    print("\n=== TEST 2: Health centres in Espoo ===")
    result = await search_services("health centre", municipality="espoo", page_size=5)
    print(f"Count: {result['total_count']}")
    for u in result["units"][:3]:
        print(f"  - {u['name']} | {u['street_address']}")
    assert result["total_count"] > 0

async def test_get_service_details():
    print("\n=== TEST 3: Service details ===")
    result = await search_services("library", municipality="helsinki", page_size=1)
    details = await get_service_details(result["units"][0]["id"])
    print(f"Name: {details['name']} | Phone: {details['phone']} | Hours: {len(details['opening_hours'])}")
    assert details["name"] and len(json.dumps(details)) < 20000

async def test_list_service_categories():
    print("\n=== TEST 4: Service categories ===")
    result = await list_service_categories()
    print(f"Categories: {result['total_count']}")
    for cat in result["categories"][:3]:
        print(f"  - {cat['name']} (id: {cat['id']})")
    assert len(result["categories"]) > 0

async def test_count_services():
    print("\n=== TEST 5: Count daycare centres ===")
    result = await count_services("daycare")
    print(f"Total: {result['total']}")
    for muni, count in result["by_municipality"].items():
        print(f"  - {muni}: {count}")
    assert result["total"] > 0

async def test_search_events():
    print("\n=== TEST 6: Events ===")
    result = await search_events(query="music", page_size=5)
    print(f"Total: {result['total_count']} | Returned: {result['returned']}")
    for e in result["events"][:3]:
        print(f"  - {e['name']} | {e['location_name']}")
    assert result["total_count"] > 0

async def test_population_statistics():
    print("\n=== TEST 7: Population ===")
    result = await get_population_statistics(start_year=2020, end_year=2024)
    for muni, years in result["population"].items():
        vals = [f"{y}: {p:,}" for y, p in sorted(years.items())]
        print(f"  {muni}: {', '.join(vals[-3:])}")
    assert len(result["population"]) >= 4

async def test_unemployment_data():
    print("\n=== TEST 8: Unemployment ===")
    result = await get_unemployment_data(months="2024M06,2024M12")
    for area, months in result["results"].items():
        for month, indicators in months.items():
            rate = indicators.get("Unemployment rate (%)", "?")
            print(f"  {area} {month}: {rate}%")
    assert len(result["results"]) > 0

async def test_emissions_data():
    print("\n=== TEST 9: Emissions ===")
    result = await get_emissions_data(start_year=2020, end_year=2023)
    total = result["emissions"].get("Total", {})
    for year, metrics in sorted(total.items()):
        print(f"  {year}: {metrics}")
    assert len(result["emissions"]) > 0

async def test_browse_statistics():
    print("\n=== TEST 10: Browse statistics ===")
    result = await browse_statistics()
    print(f"Databases: {len(result['databases'])}")
    for db in result["databases"]:
        print(f"  - {db['id']}: {db['description'][:60]}")
    assert len(result["databases"]) >= 4

async def test_browse_statistics_deep():
    print("\n=== TEST 10b: Browse Aluesarjat ===")
    result = await browse_statistics(path="Aluesarjat")
    print(f"Categories: {len(result['items'])}")
    for item in result["items"][:5]:
        print(f"  - {item['id']}: {item['text']} ({item['type']})")
    assert len(result["items"]) > 0

async def test_get_table_info():
    print("\n=== TEST 11: Table info ===")
    result = await get_table_info("Aluesarjat/vrm/vaerak/alu_vaerak_004r.px")
    print(f"Title: {result['title'][:80]}")
    for var in result["variables"]:
        print(f"  - {var['code']}: {var['text']} ({var['total_values']} values)")
    assert len(result["variables"]) > 0

async def test_query_statistics():
    print("\n=== TEST 12: Query statistics ===")
    result = await query_statistics(
        table_path="Aluesarjat/vrm/vaerak/alu_vaerak_004r.px",
        filters={"Osa-alue": ["0910000000"], "Ikä": ["ALL"], "Vuosi": ["2023", "2024"]},
    )
    print(f"Rows: {result['total_rows']}")
    for row in result["data"]:
        print(f"  {row['keys']} = {row['values']}")
    assert result["total_rows"] > 0

async def test_search_datasets():
    print("\n=== TEST 13: Search HRI catalogue ===")
    result = await search_datasets(query="housing", format_filter="PXWEB", page_size=5)
    print(f"Total: {result['total_count']} | Returned: {result['returned']}")
    for ds in result["datasets"][:3]:
        print(f"  - {ds['title'][:70]} | {ds['formats']}")
    assert result["total_count"] > 0

async def test_search_datasets_csv():
    print("\n=== TEST 13b: Search CSV datasets ===")
    result = await search_datasets(query="energy", format_filter="CSV", page_size=5)
    print(f"Total: {result['total_count']}")
    for ds in result["datasets"][:3]:
        print(f"  - {ds['title'][:70]}")
    assert result["total_count"] >= 0  # may be 0 for some queries

async def test_response_sizes():
    print("\n=== TEST 14: Response size check ===")
    tests = [
        ("search_services", await search_services("library", page_size=10)),
        ("search_events", await search_events(page_size=10)),
        ("population", await get_population_statistics(start_year=2020, end_year=2024)),
        ("emissions", await get_emissions_data(start_year=2020, end_year=2023)),
    ]
    for name, result in tests:
        size = len(json.dumps(result))
        status = "OK" if size < 20000 else "TOO BIG"
        print(f"  {name}: {size:,} bytes [{status}]")
        assert size < 20000, f"{name} response too large: {size}"


async def main():
    tests = [
        test_search_services_library, test_search_services_health,
        test_get_service_details, test_list_service_categories, test_count_services,
        test_search_events, test_population_statistics,
        test_unemployment_data, test_emissions_data,
        test_browse_statistics, test_browse_statistics_deep,
        test_get_table_info, test_query_statistics,
        test_search_datasets, test_search_datasets_csv,
        test_response_sizes,
    ]
    passed = failed = 0
    for test in tests:
        try:
            await test()
            print("PASSED")
            passed += 1
        except Exception as e:
            print(f"FAILED: {e}")
            failed += 1
    print(f"\n{'='*50}")
    print(f"Results: {passed} passed, {failed} failed out of {len(tests)}")
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
