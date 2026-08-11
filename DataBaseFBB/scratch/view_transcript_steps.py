import json

def view_steps():
    log_path = r"C:\Users\jjvar\.gemini\antigravity\brain\4b569ba8-ec46-4f5c-bb0e-449b43367ae1\.system_generated\logs\transcript_full.jsonl"
    with open(log_path, encoding='utf-8', errors='ignore') as f:
        for line in f:
            try:
                obj = json.loads(line)
                step = obj.get('step_index')
                if step in [1879, 1984]:
                    print(f"=== STEP {step} ({obj.get('source')}) ===")
                    print("Content:")
                    print(obj.get('content'))
                    print("\nThinking:")
                    print(obj.get('thinking'))
                    print("="*80)
            except Exception as e:
                pass

if __name__ == '__main__':
    view_steps()
