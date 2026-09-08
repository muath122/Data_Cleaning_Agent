import pandas as pd

from schema_agent.schema_agent import detect_schema


df = pd.read_excel("data/test.xlsx")

standardized_df, report = detect_schema(df)


print("\nORIGINAL COLUMNS")
print("=" * 60)

for column in df.columns:
    print(column)


print("\nSTANDARDIZED COLUMNS")
print("=" * 60)

for column in standardized_df.columns:
    print(column)