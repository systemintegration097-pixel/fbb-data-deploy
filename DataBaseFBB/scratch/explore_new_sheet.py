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
    
    # Search for escaped quotes like \\"Active Zones\\" or \"Active Zones\"
    # Let's search for the term as a raw substring: 'Active Zones'
    for term in ["Active Zones", "List of Boxes", "Staff"]:
        # Find all occurrences of the term in HTML
        pos = html.find(term)
        while pos != -1:
            print(f"\n--- Found '{term}' at position {pos} ---")
            # Print 150 characters before and after
            print(html[max(0, pos-150):pos+150])
            pos = html.find(term, pos+1)
            
except Exception as e:
    print("Error:", e)
