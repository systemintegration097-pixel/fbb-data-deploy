with open("scratch/edit.html", "r", encoding="utf-8") as f:
    html = f.read()

pos = html.find("ZONAS")
if pos != -1:
    snippet = html[max(0, pos-1000):min(len(html), pos+2000)]
    print("=== Snippet ===")
    print(snippet)
else:
    print("ZONAS not found")
