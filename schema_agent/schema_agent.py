import pandas as pd

from schema_agent.context_builder import build_schema_context
from schema_agent.qwen_schema_analyzer import analyze_schema_with_qwen


def detect_schema(df: pd.DataFrame):
    """
    Detect and standardize the schema of a DataFrame.

    Returns:
        standardized_df:
            A copy of the DataFrame with canonical column names.

        schema_report:
            Qwen's schema analysis for all columns.
    """

    # 1. Build context about the dataset columns
    context = build_schema_context(df)

    # 2. Let Qwen understand the schema
    schema_report = analyze_schema_with_qwen(context)

    # 3. Work on a copy so we don't modify the original DataFrame
    standardized_df = df.copy()

    # 4. Build the new list of column names
    new_column_names = []

    for column in schema_report["columns"]:

        canonical_name = column["canonical_name"]
        original_name = column["original_name"]

        # Empty columns have no canonical name.
        # Keep their original name for now.
        if canonical_name is None:
            new_column_names.append(original_name)
        else:
            new_column_names.append(canonical_name)

    # 5. Apply the canonical names to the DataFrame
    standardized_df.columns = new_column_names

    return standardized_df, schema_report