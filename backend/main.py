import os
import json
import uuid
from typing import Optional
from uuid import UUID


from dotenv import load_dotenv
load_dotenv()

from fastapi import (
    FastAPI,
    Depends,
    Form,
    File,
    UploadFile,
    WebSocket,
    WebSocketDisconnect
)
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware

from backend.orchestrator import run_pipeline
from backend.auth_guard import require_auth
from backend.auth import router as auth_router

from backend.session_manager import SessionManager
from backend.schemas import CreateSessionResponse

# ----------------------------------
# APP
# ----------------------------------
app = FastAPI(
    title="Agentic Debug Assistant",
    version="0.3.0"  # bumped version
)

manager = SessionManager()

# ----------------------------------
# MIDDLEWARE
# ----------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # dev only
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(
    SessionMiddleware,
    secret_key="super-session-secret-key"
)

# ----------------------------------
# AUTH ROUTES
# ----------------------------------
app.include_router(auth_router, prefix="/auth")

# ----------------------------------
# HEALTH
# ----------------------------------
@app.get("/health")
def health_check():
    return {"status": "ok"}

# ----------------------------------
# CREATE COLLAB SESSION (NEW)
# ----------------------------------
@app.post("/session", response_model=CreateSessionResponse)
def create_session():
    session_id = manager.create_session()
    return {
        "session_id": session_id,
        "join_url": f"/session/{session_id}"
    }

# ----------------------------------
# WEBSOCKET: REAL-TIME COLLAB (NEW)
# ----------------------------------
@app.websocket("/ws/session/{session_id}")
async def websocket_session(websocket: WebSocket, session_id: str):
    session = manager.get_session(session_id)
    if not session:
        await websocket.close(code=1008)
        return

    await websocket.accept()

    client_id = str(uuid.uuid4())[:8]
    manager.add_client(session_id, client_id, websocket)

    # Send initial state
    await websocket.send_json({
        "type": "init",
        "client_id": client_id,
        "code": manager.get_code(session_id),
        "logs": manager.sessions[session_id].get("current_logs", "")
    })


    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)

            # ----------------------------
            # CODE UPDATE EVENT
            # ----------------------------
            if message["type"] == "code_update":
                new_code = message["code"]
                manager.update_code(session_id, new_code)

                # Broadcast to other clients
                for cid, ws in manager.get_clients(session_id).items():
                    if cid != client_id:
                        await ws.send_json({
                            "type": "code_update",
                            "code": new_code,
                            "updated_by": client_id
                        })
                from backend.history import save_code_version

                save_code_version(
                    session_id=session_id,
                    code=new_code,
                    logs=manager.sessions[session_id].get("current_logs", "")
                )
            elif message["type"] == "logs_update":
                new_logs = message["logs"]

                # store logs in session (add this field)
                manager.sessions[session_id]["current_logs"] = new_logs

                for cid, ws in manager.get_clients(session_id).items():
                    if cid != client_id:
                        await ws.send_json({
                            "type": "logs_update",
                            "logs": new_logs,
                            "updated_by": client_id
                        })
                from backend.history import save_code_version

                save_code_version(
                    session_id=session_id,
                    code=new_code,
                    logs=manager.sessions[session_id].get("current_logs", "")
                )
            elif message["type"] == "analyze_request":
                from backend.orchestrator import run_pipeline
                from backend.errors import log_error, update_error_pattern

                result = run_pipeline(
                    code=manager.sessions[session_id]["current_code"],
                    logs=manager.sessions[session_id].get("current_logs", ""),
                    image=None
                )

                # persist error + pattern
                log_error(
                    session_id=str(session_id),
                    message=result["error_summary"]["message"],
                    root_cause=result["error_summary"]["root_cause"]
                )

                update_error_pattern(
                    message=result["error_summary"]["message"],
                    root_cause=result["error_summary"]["root_cause"]
                )

                # broadcast result to ALL clients
                for ws in manager.get_clients(session_id).values():
                    await ws.send_json({
                        "type": "analyze_result",
                        "result": result
                    })

    except WebSocketDisconnect:
        manager.remove_client(session_id, client_id)

# ----------------------------------
# ANALYZE (UNCHANGED)
# ----------------------------------
@app.post("/analyze")
async def analyze(
    code: str = Form(""),
    logs: str = Form(""),
    session_id: Optional[str] = Form(None),
    image: Optional[UploadFile] = File(None),
    user=Depends(require_auth)
):
    print("🔍 CODE RECEIVED:", code[:100])
    print("🔍 LOGS RECEIVED:", logs)
    print("🔍 IMAGE RECEIVED:", bool(image))
    print("🔍 SESSION ID RECEIVED:", session_id)

    image_bytes = await image.read() if image else None

    result = run_pipeline(
        code=code,
        logs=logs,
        image=image_bytes
    )

    # -------------------------------
    # SAFE SESSION_ID HANDLING
    # -------------------------------
    session_uuid = None
    if session_id and session_id != "null":
        try:
            session_uuid = UUID(session_id)
        except ValueError:
            session_uuid = None  # invalid UUID, ignore safely

    # -------------------------------
    # ERROR PERSISTENCE (SAFE)
    # -------------------------------
    if session_uuid:
        from backend.errors import log_error, update_error_pattern

        log_error(
            session_id=session_uuid,
            message=result["error_summary"]["message"],
            root_cause=result["error_summary"]["root_cause"]
        )

        update_error_pattern(
            message=result["error_summary"]["message"],
            root_cause=result["error_summary"]["root_cause"]
        )

    return {
        "error_summary": result["error_summary"],
        "error_type": result["error_type"],
        "severity": result["severity"],
        "fixed_code": result["fixed_code"],
        "explanation": result["explanation"]
    }

# ----------------------------------
# CURRENT USER (UNCHANGED)
# ----------------------------------
@app.get("/me")
def get_me(user=Depends(require_auth)):
    return {
        "email": user["email"],
        "name": user.get("name"),
        "picture": user.get("picture")
    }
