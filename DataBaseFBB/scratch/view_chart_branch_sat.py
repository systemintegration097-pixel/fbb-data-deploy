import os

def find_chart_branch_sat():
    path = "static/js/app.js"
    if not os.path.exists(path):
        print("app.js not found")
        return
    with open(path, "r", encoding="utf-8") as f:
        lines = f.readlines()
        
    for i, line in enumerate(lines):
        if "chart-branch-saturation" in line:
            print(f"Line {i+1}:")
            start = max(0, i - 5)
            end = min(len(lines), i + 40)
            for j in range(start, end):
                print(f"  {j+1}: {lines[j].rstrip()}")
            print("-" * 20)

if __name__ == "__main__":
    find_chart_branch_sat()
