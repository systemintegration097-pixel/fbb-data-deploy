import urllib.request
import re

url = "https://docs.google.com/spreadsheets/d/1PlyqsqBgSUDY5acwGjPqd_PZYkir-Cl55xD2uvF9_aQ/edit"

try:
    req = urllib.request.Request(
        url, 
        headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    )
    with urllib.request.urlopen(req) as response:
        html = response.read().decode('utf-8')
    
    print("Downloaded HTML length:", len(html))
    
    # Google Sheets HTML script tag contains the bootstrap data with sheet info.
    # Let's search for sheetId and title patterns using a regular expression.
    # The pattern is: [index, status, "GID", [{"1":[[0,0,"Tab Name"]...
    # Let's search for the pattern or print matches.
    matches = re.finditer(r'\[\d+,\d+,\s*\"(\d+)\",\s*\[\s*\{\s*\"1\"\s*:\s*\[\s*\[\s*0\s*,\s*0\s*,\s*\"([^\"]+)\"', html)
    print("Found GIDs:")
    for match in matches:
        print(f"GID: {match.group(1)}, Name: {match.group(2)}")
        
    # Let's also search for all occurrences of word "Staff" or "Zona" in the GID blocks
    # by matching '\"(\d+)\",[^\]]*\"([^\"]+)\"' or similar
    # Google Sheets uses standard JSON for bootstrap data.
    # Let's search for escaped quotes tab captions.
    # E.g. [index, 0, "GID", [{"1":[[0, 0, "TabName"]
    # The escaped sequence is `\"GID\"` and `\"TabName\"`
    matches_esc = re.finditer(r'\\\"(\d+)\\\"\s*,\s*\[\s*\{\s*\\\"1\\\"\s*:\s*\[\s*\[\s*0\s*,\s*0\s*,\s*\\\"([^\\\"]+)\\\"', html)
    print("Found GIDs (escaped format):")
    gids_dict = {}
    for match in matches_esc:
        print(f"GID: {match.group(1)}, Name: {match.group(2)}")
        gids_dict[match.group(2)] = match.group(1)
        
    # Print occurrences of tab names if not found
    for term in ["Active Zones", "List of Boxes", "Staff", "Zones", "Personal"]:
        pos = html.find(term)
        if pos != -1:
            print(f"Found '{term}' at position {pos}")
            
except Exception as e:
    print("Error:", e)
