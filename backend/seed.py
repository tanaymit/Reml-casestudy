"""Run ingest standalone: python seed.py"""
from app.ingest import run_ingest

if __name__ == "__main__":
    used, dropped = run_ingest()
    print(f"Ingest complete: {used} used, {dropped} dropped")
