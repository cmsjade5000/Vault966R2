from fastapi import APIRouter

from api.config import settings
from api.db import engine

router = APIRouter(tags=["health"])


def _masked_dsn() -> str:
    url = engine.url
    try:
        return url.render_as_string(hide_password=True)
    except AttributeError:
        return str(url)


@router.get("/health")
def health():
    url = engine.url
    return {
        "status": "ok",
        "app_name": settings.app_name,
        "database": {
            "driver": url.get_backend_name(),
            "dsn": _masked_dsn(),
        },
    }
