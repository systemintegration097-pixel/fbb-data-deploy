import os

def find_lines():
    path = "static/js/app.js"
    if not os.path.exists(path):
        print("app.js not found")
        return
    with open(path, "r", encoding="utf-8") as f:
        lines = f.readlines()
        
    print(f"Total lines in app.js: {len(lines)}")
    
    # Let's search for occurrences of chart-incidents-monthly and chart-incidents-site
    targets = ["chart-incidents-monthly", "chart-incidents-site", "incidents-section", "chart-customer-ratio"]
    for target in targets:
        print(f"\n--- Searching for: {target} ---")
        for i, line in enumerate(lines):
            if target in line:
                # print 3 lines before and 3 lines after
                start = max(0, i - 2)
                end = min(len(lines), i + 6)
                print(f"Line {i+1}:")
                for j in range(start, end):
                    print(f"  {j+1}: {lines[j].rstrip()}")
                print("-" * 20)

if __name__ == "__main__":
    find_lines()
