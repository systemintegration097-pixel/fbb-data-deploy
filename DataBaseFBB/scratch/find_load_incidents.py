import os

def find():
    path = "static/js/app.js"
    with open(path, "r", encoding="utf-8") as f:
        lines = f.readlines()
    for i, line in enumerate(lines):
        if "async function loadIncidentsReport" in line:
            print(f"loadIncidentsReport starts at line {i+1}")
            for j in range(i, min(len(lines), i + 70)):
                print(f"  {j+1}: {lines[j].rstrip()}")
            break

if __name__ == "__main__":
    find()
