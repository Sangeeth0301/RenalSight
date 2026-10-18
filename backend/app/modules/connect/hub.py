"""In-memory WebSocket hub: who is connected to which thread, and broadcasting to them.

Single-process only (fine for localhost). For several server processes this would move to Redis pub/sub.
"""
from __future__ import annotations

from collections import defaultdict

from fastapi import WebSocket


class Hub:
    def __init__(self):
        self.rooms: dict[int, list[tuple[WebSocket, int]]] = defaultdict(list)

    def add(self, thread_id: int, ws: WebSocket, user_id: int):
        self.rooms[thread_id].append((ws, user_id))

    def remove(self, thread_id: int, ws: WebSocket):
        self.rooms[thread_id] = [(w, u) for w, u in self.rooms[thread_id] if w is not ws]
        if not self.rooms[thread_id]:
            self.rooms.pop(thread_id, None)

    def online_users(self, thread_id: int) -> set[int]:
        return {u for _, u in self.rooms.get(thread_id, [])}

    def is_online(self, thread_id: int, user_id: int) -> bool:
        return user_id in self.online_users(thread_id)

    async def broadcast(self, thread_id: int, payload: dict, exclude: WebSocket | None = None):
        dead = []
        for ws, uid in list(self.rooms.get(thread_id, [])):
            if ws is exclude:
                continue
            try:
                await ws.send_json(payload)
            except Exception:       # client vanished
                dead.append(ws)
        for ws in dead:
            self.remove(thread_id, ws)


hub = Hub()
