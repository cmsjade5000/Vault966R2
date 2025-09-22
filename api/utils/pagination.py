from collections.abc import Sequence
from typing import Tuple, TypeVar

from sqlalchemy.orm import Query

T = TypeVar("T")


def paginate(query: Query, page: int, page_size: int) -> Tuple[Sequence[T], int]:
    """Return sliced results and total count for a SQLAlchemy query."""
    if page < 1:
        page = 1
    if page_size < 1:
        page_size = 1

    total = query.order_by(None).count()
    items = query.offset((page - 1) * page_size).limit(page_size).all()
    return items, total
