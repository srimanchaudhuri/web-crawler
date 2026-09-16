from pathlib import Path
import sqlite3


DB_PATH = Path("data/crawler.db")


def init_db() -> None:
	DB_PATH.parent.mkdir(parents=True, exist_ok=True)

	with sqlite3.connect(DB_PATH) as connection:
		connection.execute(
			"""
			CREATE TABLE IF NOT EXISTS metadata (
				id INTEGER PRIMARY KEY,
				url TEXT NOT NULL UNIQUE,
				status_code INTEGER,
				fetched_timestamp TEXT,
				status TEXT NOT NULL CHECK (status IN ('queued', 'processing', 'processed', 'failed'))
			)
			"""
		)
		connection.execute(
			""" 
            CREATE TABLE IF NOT EXISTS data (
                id INTEGER PRIMARY KEY,
                metadata_id INTEGER NOT NULL UNIQUE REFERENCES metadata(id),
                content TEXT
            )
            """
        )

	print(f"Database initialized: {DB_PATH}")


if __name__ == "__main__":
	init_db()
