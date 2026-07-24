"""
Bootstrap environment and database setup script.
"""
import pathlib
import sys

# Ensure src and root are in path
root = pathlib.Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(root / "src"))
sys.path.insert(0, str(root))

import asyncio

from database.sqlite import apply_migrations, apply_schema


async def main():
    print("Initializing SQLite database...")
    await apply_schema()
    applied = await apply_migrations()
    print(f"Applied migrations: {applied}")
    print("Bootstrap complete!")

if __name__ == "__main__":
    asyncio.run(main())
