# session_manager.py
from typing import Dict
from fastapi import WebSocket
import uuid
import time

class SessionManager:
    def __init__(self):
        self.sessions: Dict[str, dict] = {}

    def create_session(self) -> str:
        session_id = str(uuid.uuid4())
        self.sessions[session_id] = {
            "clients": {},
            "current_code": "",
            "current_logs": "", 
            "last_active": time.time()
        }
        return session_id
        

    def get_session(self, session_id: str):
        return self.sessions.get(session_id)

    def add_client(self, session_id: str, client_id: str, websocket: WebSocket):
        self.sessions[session_id]["clients"][client_id] = websocket
        self.sessions[session_id]["last_active"] = time.time()

    def remove_client(self, session_id: str, client_id: str):
        self.sessions[session_id]["clients"].pop(client_id, None)

    def update_code(self, session_id: str, code: str):
        self.sessions[session_id]["current_code"] = code
        self.sessions[session_id]["last_active"] = time.time()

    def get_code(self, session_id: str) -> str:
        return self.sessions[session_id]["current_code"]

    def get_clients(self, session_id: str):
        return self.sessions[session_id]["clients"]
