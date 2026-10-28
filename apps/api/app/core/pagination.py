"""Generic paginate() helper so every list endpoint applies limit/offset and
total-count the same way instead of reimplementing it per router."""

import math
from typing import Any, TypeVar

from pydantic import BaseModel
from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.common import Page, PageParams

SchemaT = TypeVar("SchemaT", bound=BaseModel)


async def paginate(
    db: AsyncSession,
    stmt: Select[Any],
    params: PageParams,
    schema: type[SchemaT],
    *,
    sortable_columns: dict[str, Any] | None = None,
) -> Page[SchemaT]:
    total = (await db.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()

    if params.sort_by and sortable_columns and params.sort_by in sortable_columns:
        column = sortable_columns[params.sort_by]
        stmt = stmt.order_by(column.desc() if params.sort_dir == "desc" else column.asc())

    stmt = stmt.offset(params.offset).limit(params.page_size)
    rows = (await db.execute(stmt)).scalars().all()

    return Page[SchemaT](
        items=[schema.model_validate(row) for row in rows],
        total=total,
        page=params.page,
        page_size=params.page_size,
        pages=max(1, math.ceil(total / params.page_size)),
    )
