from schema_agent.context_builder import read_excel_context


df, context = read_excel_context(
    "data/test.xlsx",
    sample_size=5
)

print("Rows:", len(df))
print("Columns:", len(df.columns))

for column in context:
    print("\n" + "=" * 60)
    print("Column:", column["column_name"])
    print("Type:", column["pandas_dtype"])
    print("Non-null:", column["non_null_count"])
    print("Unique:", column["unique_count"])
    print("Empty:", column["is_empty"])
    print("Samples:", column["sample_values"])