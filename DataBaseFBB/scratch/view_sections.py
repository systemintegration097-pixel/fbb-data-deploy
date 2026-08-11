with open("templates/index.html", encoding="utf-8") as f:
    content = f.read()

pos = content.find('<section id="incidents-section"')
if pos != -1:
    # Find the next closing section tag after this
    end_sec = content.find('</section>', pos)
    print(f"Closing section is at position {end_sec}")
    # Let's print the line number of this closing tag
    lines_before = content[:end_sec].count("\n") + 1
    print(f"Line number: {lines_before}")
    # Print 20 lines around this closing tag
    lines = content.split("\n")
    for idx in range(lines_before - 10, min(len(lines), lines_before + 10)):
        print(f"{idx+1}: {lines[idx]}")
