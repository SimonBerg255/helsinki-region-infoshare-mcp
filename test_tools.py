"""Live API tests for all tools."""
import asyncio
import json
import sys
import time

# Add parent to path so we can import tools directly
sys.path.insert(0, ".")
from tools import (
    count_services,
    get_population_statistics,
    get_service_details,
    list_service_categories,
    search_events,
    search_services,
)


async def test_search_services_library():
    print("\n=== TEST 1: Search libraries in Helsinki ===")
    t0 = time.time()
    result = await search_services("library", municipality="helsinki", page_size=5)
    elapsed = time.time() - t0
    print(f"Time: {elapsed:.2f}s")
    print(f"Total count: {result['total_count']}")
    print(f"Returned: {result['returned']}")
    for u in result["units"][:3]:
        print(f"  - {u['name']} | {u['street_address']} | {u['municipality']}")
    assert result["total_count"] > 0, "Should find libraries"
    assert elapsed < 20, "Should complete in <20s"
    size = len(json.dumps(result))
    print(f"Response size: {size} bytes")
    assert size < 20000, "Should be <20KB"


async def test_search_services_health():
    print("\n=== TEST 2: Search wheelchair-accessible health centres in Espoo ===")
    t0 = time.time()
    result = await search_services("health centre", municipality="espoo", page_size=5)
    elapsed = time.time() - t0
    print(f"Time: {elapsed:.2f}s")
    print(f"Total count: {result['total_count']}")
    for u in result["units"][:3]:
        print(f"  - {u['name']} | {u['street_address']}")
    assert result["total_count"] > 0, "Should find health centres"


async def test_search_services_freetext():
    print("\n=== TEST 3: Free text search 'museum' ===")
    t0 = time.time()
    result = await search_services("museum", municipality="helsinki", page_size=5)
    elapsed = time.time() - t0
    print(f"Time: {elapsed:.2f}s")
    print(f"Total count: {result['total_count']}")
    for u in result["units"][:3]:
        print(f"  - {u['name']} | {u['street_address']}")


async def test_get_service_details():
    print("\n=== TEST 4: Get details for a specific unit ===")
    # First find a library
    result = await search_services("library", municipality="helsinki", page_size=1)
    unit_id = result["units"][0]["id"]
    print(f"Fetching details for unit {unit_id}...")

    t0 = time.time()
    details = await get_service_details(unit_id)
    elapsed = time.time() - t0
    print(f"Time: {elapsed:.2f}s")
    print(f"Name: {details['name']}")
    print(f"Address: {details['street_address']}, {details['address_zip']}")
    print(f"Phone: {details['phone']}")
    print(f"Opening hours entries: {len(details['opening_hours'])}")
    print(f"Services offered: {details['services_offered'][:3]}")
    size = len(json.dumps(details))
    print(f"Response size: {size} bytes")
    assert elapsed < 20, "Should complete in <20s"
    assert size < 20000, "Should be <20KB"


async def test_list_service_categories():
    print("\n=== TEST 5: List service categories ===")
    t0 = time.time()
    result = await list_service_categories()
    elapsed = time.time() - t0
    print(f"Time: {elapsed:.2f}s")
    print(f"Total categories: {result['total_count']}")
    for cat in result["categories"][:5]:
        print(f"  - {cat['name']} (id: {cat['id']})")
    assert len(result["categories"]) > 0


async def test_list_service_categories_search():
    print("\n=== TEST 5b: Search service categories for 'health' ===")
    result = await list_service_categories(search="health")
    print(f"Found: {result['total_count']} categories")
    for cat in result["categories"][:5]:
        print(f"  - {cat['name']} (id: {cat['id']}, units: {cat.get('unit_count', '?')})")


async def test_search_events():
    print("\n=== TEST 6: Search events this week ===")
    t0 = time.time()
    result = await search_events(page_size=5)
    elapsed = time.time() - t0
    print(f"Time: {elapsed:.2f}s")
    print(f"Total events from today: {result['total_count']}")
    print(f"Returned: {result['returned']}")
    for e in result["events"][:3]:
        print(f"  - {e['name']} | {e['start_time'][:10] if e['start_time'] else '?'} | {e['location_name']} | {e['price']}")
    assert result["total_count"] > 0, "Should find events"
    size = len(json.dumps(result))
    print(f"Response size: {size} bytes")
    assert size < 20000, "Should be <20KB"
    assert elapsed < 20


async def test_search_events_keyword():
    print("\n=== TEST 6b: Search music events ===")
    result = await search_events(query="music", page_size=5)
    print(f"Total music events: {result['total_count']}")
    for e in result["events"][:3]:
        print(f"  - {e['name']} | {e['location_name']}")


async def test_count_services():
    print("\n=== TEST 7: Count daycare centres by municipality ===")
    t0 = time.time()
    result = await count_services("daycare")
    elapsed = time.time() - t0
    print(f"Time: {elapsed:.2f}s")
    print(f"Total daycare centres: {result['total']}")
    for muni, count in result["by_municipality"].items():
        print(f"  - {muni}: {count}")
    assert result["total"] > 0
    assert elapsed < 20


async def test_population_statistics():
    print("\n=== TEST 8: Population statistics ===")
    t0 = time.time()
    result = await get_population_statistics(start_year=2020, end_year=2024)
    elapsed = time.time() - t0
    print(f"Time: {elapsed:.2f}s")
    print(f"Data source: {result['data_source']}")
    for muni, years in result["population"].items():
        vals = [f"{y}: {p:,}" for y, p in sorted(years.items())]
        print(f"  {muni}: {', '.join(vals)}")
    assert len(result["population"]) > 0
    size = len(json.dumps(result))
    print(f"Response size: {size} bytes")
    assert size < 20000


async def main():
    tests = [
        test_search_services_library,
        test_search_services_health,
        test_search_services_freetext,
        test_get_service_details,
        test_list_service_categories,
        test_list_service_categories_search,
        test_search_events,
        test_search_events_keyword,
        test_count_services,
        test_population_statistics,
    ]

    passed = 0
    failed = 0

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
