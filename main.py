"""
Repository entry point — keeps `python main.py` working from the repo root.

The implementation lives in the `daily_fact_poster` package
(`daily_fact_poster/pipeline.py`); the Windows scheduled task and the README
both invoke this wrapper.
"""
from daily_fact_poster.pipeline import main

if __name__ == "__main__":
    main()
