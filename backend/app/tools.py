"""Tool registry: one place where every capability is defined once.

The same function is used by (a) normal REST routes (button clicks) and (b) the AI agents (tool calling),
so the AI can only quote what a tool returned. Each tool declares which roles may call it and whether it writes.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from fastapi import HTTPException
from pydantic import BaseModel, ValidationError

ALL_ROLES = ("patient", "doctor", "caregiver", "admin")


@dataclass
class Ctx:
    user: object
    db: object


@dataclass
class Tool:
    name: str
    description: str
    model: type[BaseModel]
    fn: Callable
    roles: tuple
    writes: bool = False
    module: str = ""


REGISTRY: dict[str, Tool] = {}


def tool(name: str, description: str, model: type[BaseModel], roles=ALL_ROLES, writes=False, module=""):
    def deco(fn):
        REGISTRY[name] = Tool(name, description, model, fn, tuple(roles), writes, module)
        return fn

    return deco


def run_tool(name: str, ctx: Ctx, payload: dict | BaseModel | None = None) -> dict:
    t = REGISTRY.get(name)
    if t is None:
        raise HTTPException(404, f"Unknown tool: {name}")
    if ctx.user.role not in t.roles:
        raise HTTPException(403, "Your role cannot use this tool")
    try:
        args = payload if isinstance(payload, t.model) else t.model.model_validate(payload or {})
    except ValidationError as e:
        raise HTTPException(422, e.errors(include_url=False, include_context=False))
    return t.fn(ctx, args)


def describe(role: str) -> list[dict]:
    return [{"name": t.name, "module": t.module, "description": t.description, "writes": t.writes,
             "input_schema": t.model.model_json_schema()} for t in REGISTRY.values() if role in t.roles]
