import argparse, json
from .db import init_db, SessionLocal


def main():
    parser = argparse.ArgumentParser(description="VibeScope local operations")
    parser.add_argument(
        "command",
        choices=["init", "seed", "sync", "worker-once", "warehouse", "evaluate"],
    )
    args = parser.parse_args()
    if args.command == "init":
        from alembic.config import Config
        from alembic import command
        from pathlib import Path

        command.upgrade(
            Config(str(Path(__file__).resolve().parents[1] / "alembic.ini")), "head"
        )
        init_db()
        print("Database initialized and mode identity verified")
    elif args.command == "seed":
        init_db()
        from .seed import seed_demo
        from .models import Report
        from .reporting import create_report
        from sqlalchemy import select

        with SessionLocal() as db:
            count = seed_demo(db)
            if not db.scalar(select(Report.id).limit(1)):
                create_report(db)
            print(json.dumps({"seeded": count, "mode": "demo"}))
    elif args.command == "sync":
        from .pipeline import enqueue, process_next

        with SessionLocal() as db:
            enqueue(db, "sync")
        process_next()
    elif args.command == "worker-once":
        from .pipeline import process_next

        print(process_next())
    elif args.command == "warehouse":
        from .pipeline import run_warehouse

        with SessionLocal() as db:
            print(run_warehouse(db))
    else:
        import runpy
        from pathlib import Path
        from .config import settings

        script = Path(settings.evaluation_dir) / "evaluate.py"
        if not script.exists():
            raise SystemExit("Evaluation script is not installed")
        runpy.run_path(str(script), run_name="__main__")


if __name__ == "__main__":
    main()
