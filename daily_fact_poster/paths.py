"""Single source of truth for the repository root (the package's parent dir)."""
import os

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
