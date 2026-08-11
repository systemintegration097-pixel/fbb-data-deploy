import os

# Paths to process
workspace_dir = os.path.dirname(os.path.dirname(__file__))
artifact_dir = r"C:\Users\jjvar\.gemini\antigravity\brain\4b569ba8-ec46-4f5c-bb0e-449b43367ae1"

# Target extensions for text replacements
valid_extensions = {'.py', '.html', '.css', '.js', '.md'}

replacements = {
    "Rupay": "Rupay",
    "rupay": "rupay",
    "RUPAY": "RUPAY"
}

def process_file(file_path):
    # Skip binary/database files
    ext = os.path.splitext(file_path)[1]
    if ext not in valid_extensions:
        return
        
    print(f"Processing: {file_path}")
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        original_content = content
        for search, replace in replacements.items():
            content = content.replace(search, replace)
            
        if content != original_content:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"  Updated!")
    except Exception as e:
        print(f"  Error processing: {e}")

def run_replace():
    # Process workspace directory
    for root, dirs, files in os.walk(workspace_dir):
        # Skip pycache and git folders
        if '__pycache__' in root or '.git' in root or '.gemini' in root:
            continue
        for file in files:
            file_path = os.path.join(root, file)
            process_file(file_path)
            
    # Process artifact directory
    if os.path.exists(artifact_dir):
        for root, dirs, files in os.walk(artifact_dir):
            if 'scratch' in root: # Skip scratch scripts inside artifacts if any
                continue
            for file in files:
                file_path = os.path.join(root, file)
                process_file(file_path)

if __name__ == "__main__":
    run_replace()
    print("Branding replacement completed.")
