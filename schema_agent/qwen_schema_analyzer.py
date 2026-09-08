import json

from mlx_vlm import load, generate
from mlx_vlm.prompt_utils import apply_chat_template


MODEL_ID = "mlx-community/Qwen3.5-2B-4bit"

print("Loading Qwen Schema Agent...")

model, processor = load(MODEL_ID)
config = model.config

print("Qwen Schema Agent loaded successfully.")


def build_schema_prompt(schema_context: list) -> str:
    """
    Convert the schema context into instructions for Qwen.
    """

    context_json = json.dumps(
        schema_context,
        ensure_ascii=False,
        indent=2
    )

    prompt = f"""
You are a Schema Detection and Column Mapping Agent for tabular datasets.

Your ONLY responsibility is to understand the schema of the dataset.

Do NOT clean, modify, standardize, or correct row values.
Other agents will handle data cleaning later.

For every column, determine:

1. original_name
2. canonical_name
3. semantic column_type
4. confidence score

Use ALL available context:
- column name
- sample values
- pandas dtype
- surrounding columns
- relationships between columns


CANONICAL NAME RULES

Canonical names must:
- be in English
- use snake_case
- clearly describe the meaning of the field
- map semantically equivalent columns to the same name

Examples:

"E-mail"
"Email"
"Email Address"
"البريد الإلكتروني"

→ email


"University"
"اسم الجامعة"
"الجامعة"

→ university


"Major"
"Specialization"
"التخصص"

→ major


IMPORTANT:
Similar-looking fields are NOT always the same field.

Example:

"University Email"
→ university_email

"Personal Email"
→ personal_email

"Email"
→ email

Do not merge these unless the meaning is truly the same.


REPEATED ENTITY RULE

Numbers such as 2, 3, 4, 5 may represent repeated team members.

Example:

Email 2 → email_2
University 2 → university_2
Major 2 → major_2

Preserve the number when it represents a different person or repeated entity.

However, do NOT add a numeric suffix merely because two questions are related.

Example:

"Have you previously participated with this idea?"
→ participated_with_idea

"If yes, where did you participate with this idea?"
→ previous_participation_event

These represent different information and must have different semantic names.


COLUMN TYPE RULES

column_type means the SEMANTIC meaning of the data,
NOT simply the pandas dtype.

Use one of these types when appropriate:

name
email
phone
datetime
integer
float
boolean
categorical
multi_select
free_text
identifier
url
string
empty
other

Choose the semantic type based on how the values are used, not only their technical dtype.

- categorical:
  A single value is selected from a limited/repeated set of categories.
  Examples: gender, university, major, usage frequency, referral source.

- multi_select:
  A row may contain multiple selected categories in the same cell.
  Example: "ChatGPT, Gemini, Claude"

- free_text:
  Open-ended natural language responses such as descriptions, explanations,
  comments, feedback, or reasons.

- identifier:
  Codes or IDs used to uniquely identify an entity.
  Examples: university_id, student_id, registration_id.
  Do NOT classify ordinary names such as team names as identifiers.

- string:
  General text that does not fit a more specific semantic type.


Examples:

Email → email
Phone Number → phone
Timestamp → datetime
University → categorical
Major → categorical
College → categorical
Gender → categorical
Idea Description → free_text
Full Name → name

Questions whose values represent Yes/No, True/False,
Agree/Disagree or equivalent binary answers should usually be:

boolean


EMPTY COLUMN RULE

If a column has no non-null values:

canonical_name must be null
column_type must be "empty"

Do NOT invent a name for an empty placeholder column.


CONFIDENCE

confidence must be between 0 and 1.

Use 1.0 only when the meaning is essentially certain.
Use lower confidence when:
- the column name is vague
- sample values are ambiguous
- multiple interpretations are plausible


NEW COLUMNS

If a completely new concept appears that has never been seen before,
infer its meaning and create a concise English snake_case canonical name.

Do NOT require the field to exist in a predefined list.


Return JSON ONLY.
No markdown.
No explanation outside the JSON.

Return exactly this structure:

{{
  "columns": [
    {{
      "column_index": 0,
      "original_name": "original column name",
      "canonical_name": "canonical_name",
      "column_type": "semantic_type",
      "confidence": 0.95
    }}
  ]
}}

Schema context:

{context_json}
"""


    return prompt


def analyze_schema_with_qwen(schema_context: list) -> dict:
    """
    Send the schema context to Qwen and return the detected schema.
    """

    prompt = build_schema_prompt(schema_context)

    formatted_prompt = apply_chat_template(
        processor,
        config,
        prompt,
        num_images=0
    )

    output = generate(
        model,
        processor,
        formatted_prompt,
        max_tokens=4000,
        temperature=0.0,
        verbose=False
    )

    response_text = output.text.strip()

    result = json.loads(response_text)

    for column in result["columns"]:
        original_context = schema_context[column["column_index"]]
    
        if original_context["is_empty"]:
            column["canonical_name"] = None
            column["column_type"] = "empty"
            column["confidence"] = 1.0
    
    return result