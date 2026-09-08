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

test_context = [
    {
        "column_index": 0,
        "column_name": "E-mail",
        "pandas_dtype": "object",
        "non_null_count": 100,
        "unique_count": 100,
        "sample_values": [
            "user@gmail.com",
            "student@uj.edu.sa"
        ],
        "is_empty": False
    },
    {
        "column_index": 1,
        "column_name": "University Email",
        "pandas_dtype": "object",
        "non_null_count": 100,
        "unique_count": 100,
        "sample_values": [
            "1234567@uj.edu.sa",
            "2345678@uj.edu.sa"
        ],
        "is_empty": False
    },
    {
        "column_index": 2,
        "column_name": "اسم الجامعة",
        "pandas_dtype": "object",
        "non_null_count": 100,
        "unique_count": 4,
        "sample_values": [
            "جامعة جدة",
            "جامعة الملك عبدالعزيز"
        ],
        "is_empty": False
    }
]


result = analyze_schema_with_qwen(test.xlsx)

print_schema_result(result)