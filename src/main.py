import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))
import uvicorn

from src.config import settings

if __name__ == "__main__":
    uvicorn.run(
        "src.api.main:app",
        host=settings.api.host,
        port=settings.api.port,
        reload=settings.api.reload,
    )
