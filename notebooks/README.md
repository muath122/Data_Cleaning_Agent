# Original text-cleaning notebook

`text_cleaning_agent4.ipynb` preserves the original Agent 4 experiment with execution
outputs cleared. Reusable code now lives in `data_cleaning_agent/stages/text.py`;
use the CLI examples for supported workflows.

The notebook is a historical reference, not the production entry point. Its original
code scans ZIP-extracted files, guesses target columns from keywords, and includes
sentiment, topics, and PII masking by default. It may overwrite its own generated files.
Its privacy claims are too broad: original personal data remains in exported columns.
The new stage requires explicit columns and makes enrichment/masking optional.

Do not commit outputs or real datasets. Install Jupyter separately if you need to
open the experiment; it is not a dependency of the application.
