                                                 

from __future__ import annotations

import asyncio
import json
from typing import Any

try:
    from websockets.asyncio.client import connect as websocket_connect
except ImportError:                                 
    from websockets import connect as websocket_connect


class NetworkClient:
    def __init__(self, url: str) -> None:
                                                                                
        self.url = url
        self.websocket: Any | None = None
        self.events: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        self._listener_task: asyncio.Task[None] | None = None
        self._send_lock = asyncio.Lock()
        self.player_id = ""

    @property
    def connected(self) -> bool:
        return self.websocket is not None

    async def connect(self) -> None:
                                                                                
        if self.connected:
            return
        self.websocket = await websocket_connect(
            self.url,
            open_timeout=10,
            ping_interval=20,
            ping_timeout=20,
            close_timeout=3,
        )
        self._listener_task = asyncio.create_task(self._listen())

    async def send(self, action: str, **payload: Any) -> None:
                                                                              
        if self.websocket is None:
            raise ConnectionError("サーバーに接続されていません。")
        message = json.dumps({"action": action, **payload}, ensure_ascii=False)
        async with self._send_lock:
            await self.websocket.send(message)

    async def close(self) -> None:
                                                                                  
        websocket = self.websocket
        self.websocket = None
        if websocket is not None:
            try:
                await websocket.close()
            except Exception:
                pass
        if self._listener_task:
            self._listener_task.cancel()
            try:
                await self._listener_task
            except (asyncio.CancelledError, Exception):
                pass
        self._listener_task = None

    async def _listen(self) -> None:
                                                                                
                                                          
        assert self.websocket is not None
        try:
            async for raw_message in self.websocket:
                if isinstance(raw_message, bytes):
                    raw_message = raw_message.decode("utf-8")
                message = json.loads(raw_message)
                if message.get("type") == "hello":
                    self.player_id = str(message.get("player_id", ""))
                await self.events.put(message)
        except asyncio.CancelledError:
            raise
        except Exception:
            await self.events.put(
                {
                    "type": "connection_lost",
                    "message": "サーバーとの接続が切れました。",
                }
            )
        finally:
            self.websocket = None
