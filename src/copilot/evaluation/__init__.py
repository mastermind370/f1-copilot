"""Evaluation harness: retrieval quality, refusal behavior, citations, and faithfulness.

Pure metric functions live in metrics.py. Everything that touches models lives in runner.py
and faithfulness.py behind small interfaces, so the metrics themselves are unit-tested
without downloading anything.
"""
