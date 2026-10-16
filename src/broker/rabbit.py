import asyncio
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent.parent))

from src.broker.consumer import app


async def main() -> None:
    await app.run()


if __name__ == "__main__":
    asyncio.run(main())
