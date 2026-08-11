import re

def view_code():
    print("=== app.py ===")
    with open('app.py', encoding='utf-8') as f:
        app_content = f.read()
    
    app_matches = re.findall(r'@app\.route\("/api/charts/branch-capacity-stacked".*?\n\s*def\s+\w+\(.*?\):.*?(?=\n\S|$)', app_content, re.DOTALL)
    for m in app_matches:
        print(m)
        print("-" * 50)
        
    print("\n=== db_manager.py ===")
    with open('db_manager.py', encoding='utf-8') as f:
        db_content = f.read()
        
    db_matches = re.findall(r'def get_branch_capacity_stacked_report\(.*?\):.*?(?=\n\s*@|$)', db_content, re.DOTALL)
    for m in db_matches:
        print(m)
        print("-" * 50)

if __name__ == '__main__':
    view_code()
