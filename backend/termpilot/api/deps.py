"""Shared FastAPI dependencies. Tests override the factories below."""

from __future__ import annotations

from functools import lru_cache
from typing import Annotated

from fastapi import Depends

from termpilot.campus.gateway import CampusGateway, build_gateway
from termpilot.llm.client import ChatModel, build_chat_model
from termpilot.security.deps import AppSettings, CurrentStudent, DbSession  # noqa: F401  (re-exported)
from termpilot.settings import get_settings


@lru_cache
def _gateway() -> CampusGateway:
    return build_gateway(get_settings())


@lru_cache
def _chat_model() -> ChatModel:
    return build_chat_model(get_settings())


def get_gateway() -> CampusGateway:
    return _gateway()


def get_chat_model() -> ChatModel:
    return _chat_model()


Gateway = Annotated[CampusGateway, Depends(get_gateway)]
Model = Annotated[ChatModel, Depends(get_chat_model)]
