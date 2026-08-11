import pandas as pd

def analyze():
    df = pd.read_csv("scratch/List_Deployed.csv", low_memory=False)
    print("=== Column Names and Indices ===")
    for idx, col in enumerate(df.columns):
        # Translate to Excel columns (0 -> A, 26 -> AA, 27 -> AB, 32 -> AG, etc.)
        col_letter = ""
        if idx < 26:
            col_letter = chr(ord('A') + idx)
        else:
            first = chr(ord('A') + (idx // 26) - 1)
            second = chr(ord('A') + (idx % 26))
            col_letter = first + second
        print(f"Index {idx} ({col_letter}): {col}")
        
    print("\n=== Shape of data ===")
    print(df.shape)
    
    print("\n=== Unique values in Partner ===")
    print(df['Partner'].value_counts(dropna=False).head(10))
    
    print("\n=== Unique values in BRANCH ===")
    print(df['BRANCH'].value_counts(dropna=False).head(10))
    
    print("\n=== Unique values in KPI (From paid) ===")
    print(df['KPI (From paid)'].value_counts(dropna=False).head(10))
    
    print("\n=== Sample values for efficiency calculation ===")
    # Let's inspect 'Close from Paid time (hrs)', 'KPI (From paid)', 'Partner', 'BRANCH'
    print(df[['Close from Paid time (hrs)', 'KPI (From paid)', 'Partner', 'BRANCH']].head(10))

if __name__ == "__main__":
    analyze()
