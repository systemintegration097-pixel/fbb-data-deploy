import urllib.request
import json
import sys

def test_endpoint(url):
    print(f"\n--- Testing: {url} ---")
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req) as response:
            data = json.loads(response.read().decode('utf-8'))
            print("Status: SUCCESS")
            if isinstance(data, dict):
                print(f"Top-level Keys: {list(data.keys())}")
                if "kpis" in data:
                    print(f"  KPIs: {data['kpis']}")
                if "causes" in data:
                    print(f"  Causes (list/dict): Type={type(data['causes'])}, Length={len(data['causes'])}")
                    if len(data['causes']) > 0:
                        print(f"  First cause sample: {data['causes'][0] if isinstance(data['causes'], list) else list(data['causes'].items())[:2]}")
                if "outages_ranking" in data:
                    print(f"  Outages ranking length: {len(data['outages_ranking'])}")
                    if len(data['outages_ranking']) > 0:
                        print(f"  First ranking item: {data['outages_ranking'][0]}")
                if "partner_breakdown" in data:
                    print(f"  Partner breakdown length: {len(data['partner_breakdown'])}")
                    if len(data['partner_breakdown']) > 0:
                        print(f"  First partner item: {data['partner_breakdown'][0]}")
                if "detail" in data:
                    print(f"  Detail rows: {len(data['detail'])}")
                    if len(data['detail']) > 0:
                        print(f"  First detail item: {data['detail'][0]}")
                if "zone_assignments" in data:
                    print(f"  Zone assignments found: length={len(data['zone_assignments'])}")
                    if len(data['zone_assignments']) > 0:
                        print(f"  First assignment sample: {data['zone_assignments'][0]}")
            elif isinstance(data, list):
                print(f"Type: LIST, Length={len(data)}")
                if len(data) > 0:
                    print(f"First item: {data[0]}")
            return data
    except urllib.error.HTTPError as e:
        print(f"HTTP Error: {e.code} - {e.reason}")
        try:
            err_body = e.read().decode('utf-8')
            print(f"Error body: {err_body[:500]}")
        except Exception:
            pass
        return None
    except Exception as e:
        print(f"General Error: {e}")
        return None

if __name__ == "__main__":
    base_url = "http://127.0.0.1:5000"
    
    # 1. Test Filter Options API
    test_endpoint(f"{base_url}/api/filters")
    
    # 2. Test Dashboard Capacity Stacked (with and without branch filter)
    test_endpoint(f"{base_url}/api/charts/branch-capacity-stacked")
    test_endpoint(f"{base_url}/api/charts/branch-capacity-stacked?branch=LI1")
    
    # 3. Test Outages
    test_endpoint(f"{base_url}/api/incidents/outages")
    test_endpoint(f"{base_url}/api/incidents/outages?branch=LI1")
    
    # 4. Test Deployments
    test_endpoint(f"{base_url}/api/deployments/stats")
    test_endpoint(f"{base_url}/api/deployments/stats?branch=LI1")
