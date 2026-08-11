def check_braces(filename):
    with open(filename, 'r', encoding='utf-8') as f:
        content = f.read()
    
    stack = []
    lines = content.split('\n')
    
    for i, line in enumerate(lines):
        for col, char in enumerate(line):
            if char in '({[':
                stack.append((char, i + 1, col + 1))
            elif char in ')}]':
                if not stack:
                    print(f"Extra closing character '{char}' at line {i+1}, col {col+1}")
                    return False
                top, l, c = stack.pop()
                # Check match
                if (char == ')' and top != '(') or \
                   (char == '}' and top != '{') or \
                   (char == ']' and top != '['):
                    print(f"Mismatched closing '{char}' at line {i+1}, col {col+1} matching '{top}' from line {l}, col {c}")
                    return False
                    
    if stack:
        print(f"Unmatched opening characters left in stack:")
        for char, l, c in stack:
            print(f"  '{char}' at line {l}, col {c}")
        return False
        
    print("No brace/parenthesis mismatch found!")
    return True

if __name__ == "__main__":
    check_braces("static/js/app.js")
