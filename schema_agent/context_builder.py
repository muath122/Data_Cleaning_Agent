import pandas as pd


def build_schema_context(
    df: pd.DataFrame,
    sample_size: int = 5,
    max_sample_chars: int = 120
) -> list:

    columns_context = []

    for index, column_name in enumerate(df.columns):

        column = df.iloc[:, index]

        non_null_values = column.dropna()

        sample_values = []

        for value in non_null_values:

            value = str(value).strip()

            if not value:
                continue

            # Prevent extremely long text from being sent to the LLM
            if len(value) > max_sample_chars:
                value = value[:max_sample_chars] + "..."

            if value not in sample_values:
                sample_values.append(value)

            if len(sample_values) >= sample_size:
                break

        column_context = {
            "column_index": index,
            "column_name": str(column_name),
            "pandas_dtype": str(column.dtype),
            "non_null_count": int(non_null_values.shape[0]),
            "unique_count": int(non_null_values.nunique()),
            "sample_values": sample_values,
            "is_empty": non_null_values.empty
        }

        columns_context.append(column_context)

    return columns_context


def read_excel_context(
    file_path: str,
    sheet_name=0,
    sample_size: int = 5
):

    df = pd.read_excel(
        file_path,
        sheet_name=sheet_name
    )

    context = build_schema_context(
        df,
        sample_size=sample_size
    )

    return df, context