import urllib.request
import json

def test():
    print("=== Testing /api/incidents/outages ===")
    try:
        url = "http://127.0.0.1:5000/api/incidents/outages?branch=ARE&month=05/2026"
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req) as res:
            data = json.loads(res.read().decode())
            print("KPIs:", data.get("kpis"))
            print("Causes (sample 2):", data.get("causes")[:2])
            print("Outages Ranking (sample 2):", data.get("outages_ranking")[:2])
    except Exception as e:
        print("Error /api/incidents/outages:", e)

    print("\n=== Testing branch_distribution in dashboard stats ===")
    try:
        url = "http://127.0.0.1:5000/api/dashboard/stats"
        # Wait, the endpoint might be /api/dashboard or /api/dashboard/stats. Let's check from app.py.
        # In app.py: @app.route("/api/dashboard", methods=["GET"])
        url = "http://127.0.0.1:5000/api/dashboard"
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req) as res:
            data = json.loads(res.read().decode())
            print("Branch distribution sample:", data.get("branch_distribution")[:2])
    except Exception as e:
        print("Error /api/dashboard:", e)

if __name__ == "__main__":
    test()
