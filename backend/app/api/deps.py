"""FastAPI dependencies."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Request

from app.core.config import Settings, get_settings
from app.core.errors import DataUnavailableError
from app.data.repository import WindDataRepository


def get_repository(request: Request) -> WindDataRepository:
    """The repository loaded at startup (see ``app.main``)."""
    repo = getattr(request.app.state, "repository", None)
    if repo is None:
        msg = "The data snapshot is not loaded."
        raise DataUnavailableError(msg)
    return repo  # type: ignore[no-any-return]


Repo = Annotated[WindDataRepository, Depends(get_repository)]
Config = Annotated[Settings, Depends(get_settings)]
