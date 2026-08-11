import os
import pandas as pd

def explore_excel_sheets(xlsx_path):
    print(f"=== Sheets in {os.path.basename(xlsx_path)} ===")
    try:
        xl = pd.ExcelFile(xlsx_path)
        print("Sheets:", xl.sheet_names)
        for s in ['Historial Fallas', 'Historial Cortes', 'Resumen OLT', 'OLTs con Error']:
            if s in xl.sheet_names:
                df = pd.read_excel(xlsx_path, sheet_name=s, nrows=3)
                print(f"\nSheet '{s}':")
                print("Columns:", list(df.columns))
                print("Sample:\n", df.head(1))
            else:
                print(f"Sheet '{s}' not found.")
    except Exception as e:
        print("Error exploring sheet:", e)

if __name__ == "__main__":
    report_dir = "Reporte FTTH"
    excel_files = sorted([os.path.join(report_dir, f) for f in os.listdir(report_dir) if f.endswith(".xlsx")])
    if excel_files:
        explore_excel_sheets(excel_files[-1]) # Explore the latest one
    else:
        print("No Excel files found.")
