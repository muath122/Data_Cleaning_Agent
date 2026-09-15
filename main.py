"""Compatibility entry point; prefer python -m data_cleaning_agent."""

from data_cleaning_agent.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
