import os

def find_function():
    path = "static/js/app.js"
    if not os.path.exists(path):
        print("app.js not found")
        return
    with open(path, "r", encoding="utf-8") as f:
        lines = f.readlines()
        
    for i, line in enumerate(lines):
        if "function renderStackedIncidentChart" in line or "renderStackedIncidentChart = " in line or "renderStackedIncidentChart(" in line and "function" in line:
            print(f"Found renderStackedIncidentChart at line {i+1}:")
            # print next 100 lines
            end = min(len(lines), i + 120)
            for j in range(i, end):
                print(f"  {j+1}: {lines[j].rstrip()}")
            break

if __name__ == "__main__":
    find_function()
