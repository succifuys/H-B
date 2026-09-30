                                                            

from __future__ import annotations

import os
from pathlib import Path

import flet.fastapi as flet_fastapi
import uvicorn
from fastapi import WebSocket, WebSocketDisconnect

from game_server import GameHub
from launch import main as flet_main


PORT = int(os.getenv("PORT", "8000"))
                                                                       
                                                                              
os.environ.setdefault("GAME_WS_URL", f"ws://127.0.0.1:{PORT}/api/ws")
ASSETS_DIR = Path(__file__).parent / "assets"

hub = GameHub(os.getenv("DATABASE_PATH", "data/hit_and_blow.db"))
app = flet_fastapi.FastAPI(title="DNTSNE Hit & Blow Online", version="2.1.0")


@app.get("/health")
async def health() -> dict[str, object]:
                                                          
    return {
        "status": "ok",
        "online_players": len(hub.players),
        "rooms": len(hub.rooms),
    }


@app.websocket("/api/ws")
async def game_socket(websocket: WebSocket) -> None:
                                                                       
    await websocket.accept()
    player = await hub.connect(websocket)
    try:
        while True:
            payload = await websocket.receive_json()
            if not isinstance(payload, dict):
                await websocket.send_json(
                    {"type": "error", "message": "メッセージ形式が正しくありません。"}
                )
                continue
            await hub.handle(player.player_id, payload)
    except WebSocketDisconnect:
        pass
    finally:
        await hub.disconnect(player.player_id)


                                                                                  
app.mount(
    "/",
    flet_fastapi.app(
        main=flet_main,
                                                                           
                                                                             
        assets_dir=str(ASSETS_DIR),
        app_name="DNTSNE ヒット＆ブロー ONLINE",
        app_short_name="DNTSNE H&B",
        app_description="DeadNeuronsThatShouldNeverExist — リアルタイム1対1ヒット＆ブロー",
    ),
)


if __name__ == "__main__":
    uvicorn.run(app, host=os.getenv("HOST", "0.0.0.0"), port=PORT)
