import os

def find():
    path = "static/js/app.js"
    with open(path, "r", encoding="utf-8") as f:
        lines = f.readlines()
    for i, line in enumerate(lines):
        if "incidents-filter-branch" in line:
            print(f"Line {i+1}:")
            for j in range(max(0, i-2), min(len(lines), i+8)):
                print(f"  {j+1}: {lines[j].rstrip()}")
            print("-" * 20)

if __name__ == "__main__":
    find()
