import os

report_path = "nims_report.xls"
if os.path.exists(report_path):
    print(f"File size: {os.path.getsize(report_path)} bytes")
    with open(report_path, "r", encoding="utf-8", errors="ignore") as f:
        head = f.read(2000)
    print("--- FIRST 2000 CHARACTERS ---")
    print(repr(head))
else:
    print("File nims_report.xls not found!")
