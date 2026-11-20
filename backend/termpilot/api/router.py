"""Mount every route module under ``/api``."""

from __future__ import annotations

from fastapi import APIRouter

from termpilot.api.routes import academics, accounts, assistant, files, mail, planning, system

api_router = APIRouter(prefix="/api")
for module in (system, accounts, planning, academics, mail, assistant, files):
    api_router.include_router(module.router)
