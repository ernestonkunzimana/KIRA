"""conftest.py — makes the backend package importable from the tests/ directory."""
import sys
import os

# Add backend/ to sys.path so tests can import core.*, api.*, config, etc.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))
