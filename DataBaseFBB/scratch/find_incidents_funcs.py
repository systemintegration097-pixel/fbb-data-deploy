import os

def find():
    path = "static/js/app.js"
    with open(path, "r", encoding="utf-8") as f:
        lines = f.readlines()
    for i, line in enumerate(lines):
        if "incidents" in line.lower() and "function" in line:
            print(f"Line {i+1}: {line.rstrip()}")

if __name__ == "__main__":
    find()
