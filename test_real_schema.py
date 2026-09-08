from schema_agent.context_builder import read_excel_context
from schema_agent.qwen_schema_analyzer import analyze_schema_with_qwen


def print_schema_result(result):
    print("\n" + "=" * 60)
    print("SCHEMA ANALYSIS RESULT")
    print("=" * 60)

    for column in result["columns"]:
        print(f"\nColumn #{column['column_index']}")
        print("-" * 40)
        print("Original Name :", column["original_name"])
        print("Canonical Name:", column["canonical_name"])
        print("Column Type   :", column["column_type"])
        print("Confidence    :", column["confidence"])


# 1) Read Excel and build context
df, context = read_excel_context(
    "data/test.xlsx",
    sample_size=5
)

print(f"Rows: {len(df)}")
print(f"Columns: {len(df.columns)}")

# 2) Analyze the real schema with Qwen
result = analyze_schema_with_qwen(context)

# 3) Print readable output
print_schema_result(result)