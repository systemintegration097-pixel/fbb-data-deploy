import urllib.request
import re

url = "https://docs.google.com/spreadsheets/d/1nHwheTVnErmxIoPin5o5-HNGqGHqhWV64sBhJmTFhA8/edit"

try:
    req = urllib.request.Request(
        url, 
        headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    )
    with urllib.request.urlopen(req) as response:
        html = response.read().decode('utf-8')
    
    # Let's search for gid patterns or JSON configuration.
    # Google Sheets bootstrap data typically contains a JSON structure:
    # bootstrapData = {...};
    # Let's look for "bootstrapData"
    boot_pos = html.find("bootstrapData")
    if boot_pos != -1:
        print("Found bootstrapData at position:", boot_pos)
        print(html[boot_pos:boot_pos+2000])
        
    # Let's look for all matches of sheetId or similar keys
    # or search for "1296694110" which was in the URL to see where it appears and what context
    url_gid = "1296694110"
    pos = html.find(url_gid)
    while pos != -1:
        print(f"Found {url_gid} at {pos}:")
        print(html[max(0, pos-150):pos+150])
        pos = html.find(url_gid, pos+1)
        if len(html) - pos < 100:
            break
            
    # Let's search for matches of "Active Zones" and see if there are numbers like 0 or other integers nearby.
    # Often in the HTML, sheets are defined in a JSON array: [id, name, index, ...]
    # Let's search for '"Active Zones"' (with quotes) or similar.
    for term in ['"Active Zones"', 'Active Zones', '"List of Boxes"', 'List of Boxes']:
        matches = [m.start() for m in re.finditer(re.escape(term), html)]
        print(f"Occurrences of {term}: {matches}")
        for idx in matches[:3]:
            print(f"Context around {idx}:")
            print(html[max(0, idx-100):idx+100])
            
except Exception as e:
    print("Error:", e)
