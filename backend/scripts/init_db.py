"""
Database initialization wrapper.
Executes build_database.py to create schema and populate clean dataset.
"""
from backend.scripts.build_database import build_database

if __name__ == "__main__":
    build_database()
