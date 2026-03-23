"""
Simulate realistic, ambiguous user questions that an AI agent would receive.
Tests whether the tool chain can answer them end-to-end.
"""
import asyncio
import json
import sys
import time

sys.path.insert(0, ".")
from tools import (
    browse_statistics, count_services, get_emissions_data,
    get_population_statistics, get_service_details, get_table_info,
    get_unemployment_data, list_service_categories, query_statistics,
    search_datasets, search_events, search_services,
)


async def scenario_1():
    """User: 'Where can I swim in Vantaa?'
    Agent must figure out: swimming pool → service type, Vantaa → municipality"""
    print("\n=== SCENARIO 1: 'Where can I swim in Vantaa?' ===")
    result = await search_services("swimming pool", municipality="vantaa", page_size=5)
    print(f"Found {result['total_count']} swimming facilities in Vantaa")
    if result["total_count"] == 0:
        # Fallback: try free-text search
        print("  Trying free-text search...")
        result = await search_services("swim", municipality="vantaa", page_size=5)
        print(f"  Free-text found: {result['total_count']}")
    for u in result["units"][:3]:
        print(f"  - {u['name']} | {u['street_address']}")
    assert result["total_count"] > 0, "Should find swimming places"
    return True


async def scenario_2():
    """User: 'What's happening this weekend?'
    Agent must: infer Helsinki metro, use date range for upcoming weekend"""
    print("\n=== SCENARIO 2: 'What's happening this weekend?' ===")
    from datetime import date, timedelta
    today = date.today()
    # Find next Saturday
    days_until_sat = (5 - today.weekday()) % 7
    if days_until_sat == 0 and today.weekday() != 5:
        days_until_sat = 7
    saturday = today + timedelta(days=days_until_sat)
    sunday = saturday + timedelta(days=1)

    result = await search_events(
        start_date=saturday.isoformat(),
        end_date=sunday.isoformat(),
        page_size=10,
    )
    print(f"Found {result['total_count']} events this weekend ({saturday} - {sunday})")
    for e in result["events"][:5]:
        print(f"  - {e['name']} | {e['location_name']} | {e['price'] or 'price unknown'}")
    assert result["total_count"] > 0, "Should find weekend events"
    return True


async def scenario_3():
    """User: 'How has Helsinki's population changed?'
    Agent must: use population tool, show trend over years"""
    print("\n=== SCENARIO 3: 'How has Helsinki's population changed?' ===")
    result = await get_population_statistics(municipality="helsinki", start_year=2015, end_year=2024)
    pop = result["population"].get("Helsinki", {})
    print(f"Helsinki population trend:")
    years_sorted = sorted(pop.items())
    for year, count in years_sorted:
        print(f"  {year}: {count:,}")
    if len(years_sorted) >= 2:
        first = years_sorted[0][1]
        last = years_sorted[-1][1]
        growth = ((last - first) / first) * 100
        print(f"  Growth {years_sorted[0][0]}-{years_sorted[-1][0]}: {growth:.1f}%")
    assert len(pop) > 0
    return True


async def scenario_4():
    """User: 'Compare schools across cities'
    Agent must: use count_services for aggregation"""
    print("\n=== SCENARIO 4: 'Compare schools across cities' ===")
    result = await count_services("school")
    print(f"Comprehensive schools by municipality:")
    for muni, count in result["by_municipality"].items():
        print(f"  {muni}: {count}")
    print(f"  Total: {result['total']}")
    assert result["total"] > 0
    return True


async def scenario_5():
    """User: 'Is Helsinki reducing its carbon emissions?'
    Agent must: use emissions tool, show trend"""
    print("\n=== SCENARIO 5: 'Is Helsinki reducing its carbon emissions?' ===")
    result = await get_emissions_data(start_year=2015, end_year=2023)
    total = result["emissions"].get("Total", {})
    print("Helsinki total GHG emissions:")
    for year in sorted(total.keys()):
        metrics = total[year]
        total_val = metrics.get("Total (1000t CO2-eq)", "?")
        per_cap = metrics.get("Per capita (t CO2-eq)", "?")
        print(f"  {year}: {total_val} kt CO2-eq ({per_cap} t/capita)")
    assert len(total) > 0
    return True


async def scenario_6():
    """User: 'What's the unemployment situation?'
    Agent must: use unemployment tool, show recent data"""
    print("\n=== SCENARIO 6: 'What's the unemployment situation?' ===")
    result = await get_unemployment_data(months="2024M01,2024M06,2024M12")
    for area, months in result["results"].items():
        print(f"  {area}:")
        for month, indicators in sorted(months.items()):
            rate = indicators.get("Unemployment rate (%)", "?")
            seekers = indicators.get("Unemployed jobseekers", "?")
            print(f"    {month}: {rate}% ({int(seekers) if isinstance(seekers, float) else seekers} jobseekers)")
    assert len(result["results"]) > 0
    return True


async def scenario_7():
    """User: 'I need data about housing in Helsinki region'
    Agent must: navigate PxWeb tree to find housing data OR search catalogue"""
    print("\n=== SCENARIO 7: 'I need data about housing in Helsinki region' ===")

    # Approach A: Browse statistics
    print("  Approach A: Browse PxWeb tree...")
    result = await browse_statistics(path="Aluesarjat/asu")
    print(f"  Housing categories: {len(result['items'])}")
    for item in result["items"]:
        print(f"    - {item['id']}: {item['text']} ({item['type']})")

    # Approach B: Search catalogue
    print("  Approach B: Search HRI catalogue...")
    result2 = await search_datasets(query="housing", page_size=5)
    print(f"  Catalogue results: {result2['total_count']}")
    for ds in result2["datasets"][:3]:
        print(f"    - {ds['title'][:60]} | {ds['formats']}")

    assert len(result["items"]) > 0
    return True


async def scenario_8():
    """User: 'What kind of income data do you have?'
    Agent must: discover income tables via browse, then show table info"""
    print("\n=== SCENARIO 8: 'What kind of income data do you have?' ===")

    # Step 1: Browse to income category
    result = await browse_statistics(path="Aluesarjat/tul")
    print(f"  Income subcategories: {len(result['items'])}")
    for item in result["items"]:
        print(f"    - {item['id']}: {item['text']} ({item['type']})")

    # Step 2: Go deeper into one
    if result["items"]:
        first_id = result["items"][0]["id"]
        result2 = await browse_statistics(path=f"Aluesarjat/tul/{first_id}")
        print(f"  Tables in {first_id}: {len(result2['items'])}")
        for item in result2["items"][:3]:
            print(f"    - {item['id']}: {item['text'][:60]}")

        # Step 3: Get info on first table
        if result2["items"] and result2["items"][0]["type"] == "table":
            table_id = result2["items"][0]["id"]
            info = await get_table_info(f"Aluesarjat/tul/{first_id}/{table_id}")
            print(f"  Table: {info['title'][:80]}")
            for var in info["variables"]:
                print(f"    Variable: {var['code']} ({var['total_values']} values)")

    assert len(result["items"]) > 0
    return True


async def scenario_9():
    """User: 'Find me a library near Kallio'
    Agent must: search with free text since 'Kallio' is a neighborhood, not a service type"""
    print("\n=== SCENARIO 9: 'Find me a library near Kallio' ===")
    # First search for libraries in Helsinki
    result = await search_services("library", municipality="helsinki", page_size=10)
    print(f"Libraries in Helsinki: {result['total_count']}")
    # Look for ones with Kallio-area addresses
    kallio_nearby = []
    for u in result["units"]:
        addr = u.get("street_address", "").lower()
        name = u.get("name", "").lower()
        if any(k in addr or k in name for k in ["kallio", "sörnäinen", "hakaniemi", "alppila"]):
            kallio_nearby.append(u)
    if kallio_nearby:
        print(f"  Near Kallio:")
        for u in kallio_nearby:
            print(f"    - {u['name']} | {u['street_address']}")
    else:
        print(f"  Showing closest options (agent would need to present all {result['returned']} with addresses)")
        for u in result["units"][:3]:
            print(f"    - {u['name']} | {u['street_address']}")
    return True


async def scenario_10():
    """User: 'Environmental statistics for Helsinki'
    Agent must: browse environmental database"""
    print("\n=== SCENARIO 10: 'Environmental statistics for Helsinki' ===")
    result = await browse_statistics(path="Ymparistotilasto")
    print(f"Environmental categories: {len(result['items'])}")
    for item in result["items"]:
        print(f"  - {item['id']}: {item['text']} ({item['type']})")
    assert len(result["items"]) > 0
    return True


async def scenario_11():
    """User: 'How many daycare places are there compared to children?'
    Multi-step: count daycare + query population by age"""
    print("\n=== SCENARIO 11: 'How many daycare places vs children?' ===")

    # Step 1: Count daycare centres
    daycare = await count_services("daycare")
    print(f"Daycare centres: {daycare['total']}")
    for m, c in daycare["by_municipality"].items():
        print(f"  {m}: {c}")

    # Step 2: Get child population (0-6 year olds)
    pop = await query_statistics(
        table_path="Aluesarjat/vrm/vaerak/alu_vaerak_004r.px",
        filters={
            "Osa-alue": ["0910000000", "0490000000", "0920000000", "2350000000"],
            "Ikä": ["0-6"],
            "Vuosi": ["2024"],
        },
    )
    area_names = {"0910000000": "Helsinki", "0490000000": "Espoo", "0920000000": "Vantaa", "2350000000": "Kauniainen"}
    print("Children aged 0-6 (2024):")
    for row in pop["data"]:
        area = area_names.get(row["keys"][0], row["keys"][0])
        print(f"  {area}: {int(row['values'][0]):,}")

    return True


async def scenario_12():
    """User: 'Free things to do with kids'
    Agent must: search events with 'children' + is_free=True"""
    print("\n=== SCENARIO 12: 'Free things to do with kids' ===")
    result = await search_events(query="children", is_free=True, page_size=5)
    print(f"Free children's events: {result['total_count']}")
    for e in result["events"][:5]:
        print(f"  - {e['name']} | {e['location_name']} | {e['start_time'][:10] if e['start_time'] else '?'}")
    # Even if 0 results for "children", try "lapsi" (Finnish)
    if result["total_count"] == 0:
        result2 = await search_events(query="lapsi", is_free=True, page_size=5)
        print(f"  Finnish search 'lapsi': {result2['total_count']} events")
    return True


async def main():
    scenarios = [
        scenario_1, scenario_2, scenario_3, scenario_4, scenario_5,
        scenario_6, scenario_7, scenario_8, scenario_9, scenario_10,
        scenario_11, scenario_12,
    ]

    passed = failed = 0
    total_start = time.time()

    for scenario in scenarios:
        try:
            t0 = time.time()
            await scenario()
            elapsed = time.time() - t0
            print(f"PASSED ({elapsed:.1f}s)")
            passed += 1
        except Exception as e:
            print(f"FAILED: {e}")
            import traceback
            traceback.print_exc()
            failed += 1

    total_elapsed = time.time() - total_start
    print(f"\n{'='*60}")
    print(f"Agent scenarios: {passed} passed, {failed} failed out of {len(scenarios)}")
    print(f"Total time: {total_elapsed:.1f}s")
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
