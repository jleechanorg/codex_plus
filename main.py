# main.py - Import proxy app for testing
from main_sync_cffi import app

# Re-export app for test compatibility
__all__ = ['app']