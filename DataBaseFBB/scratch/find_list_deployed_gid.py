with open("scratch/edit.html", "r", encoding="utf-8") as f:
    html = f.read()

# Let's search for "List Deployed" in the JSON config of Google Sheets.
# Usually it's in a structure like: {"sheetName":"List Deployed","sheetId":12345}
# Or "List Deployed", ... "id": 12345
import re
matches = re.findall(r'"sheetName":"List Deployed"[^}]+"sheetId":(\d+)', html)
if matches:
    print("Found GID via sheetName regex:", matches)
else:
    # Let's search for "List Deployed" and print 500 chars around it in raw text
    pos = html.find("List Deployed")
    if pos != -1:
        print("Raw text snippet around List Deployed:")
        print(html[pos-300:pos+300])
        # Find GID in the surrounding text (look for numbers)
        gids = re.findall(r'(\d+)', html[pos-300:pos+300])
        print("Possible GIDs in snippet:", gids)
