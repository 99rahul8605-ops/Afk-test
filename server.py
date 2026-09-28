"""Compatibility launcher for the original project.

The maintained entry point is main.py. Running server.py now simply starts
that same application instead of importing the old/nonexistent SONALI module.
"""
import os
import sys

if __name__ == "__main__":
    os.execv(sys.executable, [sys.executable, os.path.join(os.path.dirname(__file__), "main.py")])
