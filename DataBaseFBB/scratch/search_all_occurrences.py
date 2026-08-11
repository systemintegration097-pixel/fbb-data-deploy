import re

def search():
    with open("scratch/edit.html", "r", encoding="utf-8") as f:
        html = f.read()
    
    # Let's search for List Deployed or list_deployed
    pattern = re.compile(r'List Deployed', re.IGNORECASE)
    for m in pattern.finditer(html):
        start = max(0, m.start() - 150)
        end = min(len(html), m.end() + 150)
        print(f"Occurrence at {m.start()}:")
        print(html[start:end])
        print("-" * 50)
        
    # Let's also print bootstrapData keys if found
    pos = html.find("bootstrapData")
    if pos != -1:
        print("Found bootstrapData snippet:")
        print(html[pos:pos+1000])

if __name__ == "__main__":
    search()
