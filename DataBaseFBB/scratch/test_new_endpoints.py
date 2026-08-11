import urllib.request
import json

def test_endpoint(url):
    print(f"Testing: {url}")
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req) as response:
            data = json.loads(response.read().decode('utf-8'))
            print("Status: Success!")
            if isinstance(data, dict):
                print(f"Keys: {list(data.keys())}")
                if 'kpis' in data:
                    print(f"KPIs: {data['kpis']}")
                if 'monthly_breakdown' in data:
                    print(f"Monthly breakdown length: {len(data['monthly_breakdown'])}")
                if 'site_breakdown' in data:
                    print(f"Site breakdown length: {len(data['site_breakdown'])}")
            elif isinstance(data, list):
                print(f"List length: {len(data)}")
                if len(data) > 0:
                    print(f"First item: {data[0]}")
            return True
    except Exception as e:
        print(f"Error: {e}")
        return False

if __name__ == "__main__":
    base_url = "http://127.0.0.1:5000"
    endpoints = [
        "/api/dashboard",
        "/api/charts/branch-capacity-stacked",
        "/api/incidents/stats",
        "/api/incidents/sites",
        "/api/incidents/months",
        "/api/incidents/stats?branch=LI1&month=02/2026", # Example month from database format (ENERO/FEBRERO format in sheet but mes/año is like '02/2026' or '01/2026')
        "/api/incidents/sites?branch=LI1"
    ]
    for ep in endpoints:
        # Urlencode space
        url = (base_url + ep).replace(" ", "%20")
        test_endpoint(url)
