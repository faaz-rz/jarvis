"""Local-only real-time web dashboard for the JARVIS engine."""
from __future__ import annotations

import json
import logging
import mimetypes
import os
import queue
import secrets
import threading
import time
import webbrowser
from collections import deque
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from core.config import PROJECT_ROOT, env_int
from core.ui import BaseUI


class DashboardUI(BaseUI):
    """Serve the dashboard and bridge browser events to the engine."""

    def __init__(
        self,
        callback_handler=None,
        port=None,
        open_browser=True,
        static_dir=None,
    ):
        self.callback_handler = callback_handler
        self.host = "127.0.0.1"
        self.requested_port = (
            int(port)
            if port is not None
            else env_int("JARVIS_DASHBOARD_PORT", 8765)
        )
        self.open_browser = open_browser
        self.static_dir = Path(
            static_dir or PROJECT_ROOT / "dashboard"
        ).resolve()
        self.session_token = secrets.token_urlsafe(32)
        self.messages = deque(maxlen=120)
        self.events = deque(maxlen=160)
        self._subscribers = set()
        self._subscriber_lock = threading.RLock()
        self._state_lock = threading.RLock()
        self._server = None
        self._server_thread = None
        self._started = threading.Event()
        self._stopped = threading.Event()
        self._sequence = 0
        self._stream_message = None
        self._state = {
            "status": "Starting",
            "brain_state": "booting",
            "model": "Local model",
            "backend": "local",
            "skills": [],
            "tools": [],
            "voice_enabled": False,
            "memory_enabled": False,
            "mission": None,
            "url": None,
        }

    @property
    def url(self):
        with self._state_lock:
            return self._state.get("url")

    def bind_handler(self, callback_handler):
        self.callback_handler = callback_handler

    def configure_system(
        self,
        *,
        model,
        backend,
        skills,
        tools,
        voice_enabled,
        memory_enabled,
    ):
        with self._state_lock:
            self._state.update(
                {
                    "model": str(model),
                    "backend": str(backend),
                    "skills": list(skills),
                    "tools": list(tools),
                    "voice_enabled": bool(voice_enabled),
                    "memory_enabled": bool(memory_enabled),
                }
            )
        self.emit_event(
            "system_configured",
            {
                "model": str(model),
                "backend": str(backend),
                "skill_count": len(skills),
                "tool_count": len(tools),
                "voice_enabled": bool(voice_enabled),
                "memory_enabled": bool(memory_enabled),
            },
        )

    def display_message(self, text: str, sender: str = "JARVIS"):
        message = {
            "sender": str(sender),
            "text": str(text),
            "timestamp": time.time(),
        }
        with self._state_lock:
            self.messages.append(message)
        self.emit_event("message", message)

    def set_status(self, text: str):
        status = str(text or "")
        brain_state = self._brain_state_for_status(status)
        with self._state_lock:
            self._state["status"] = status or "Ready"
            self._state["brain_state"] = brain_state
        self.emit_event(
            "brain_state",
            {
                "state": brain_state,
                "label": status or "Ready",
            },
        )

    def get_input(self) -> str:
        return ""

    def begin_stream(self, sender: str = "JARVIS"):
        self._stream_message = {
            "sender": str(sender),
            "text": "",
            "timestamp": time.time(),
        }
        with self._state_lock:
            self._state["status"] = "Responding"
            self._state["brain_state"] = "responding"
        self.emit_event("stream_start", {"sender": str(sender)})

    def append_stream(self, text: str):
        chunk = str(text)
        if self._stream_message is not None:
            self._stream_message["text"] += chunk
        self.emit_event("stream_chunk", {"text": chunk})

    def end_stream(self):
        if self._stream_message and self._stream_message["text"]:
            with self._state_lock:
                self.messages.append(dict(self._stream_message))
        self._stream_message = None
        self.emit_event("stream_end", {})

    def emit_event(self, event_type: str, data=None):
        with self._state_lock:
            payload = data if isinstance(data, dict) else {}
            if event_type == "mission_updated":
                self._state["mission"] = payload.get("mission")
            self._sequence += 1
            event = {
                "id": self._sequence,
                "type": str(event_type),
                "timestamp": time.time(),
                "data": payload,
            }
            self.events.append(event)
        with self._subscriber_lock:
            subscribers = list(self._subscribers)
        for subscriber in subscribers:
            try:
                subscriber.put_nowait(event)
            except queue.Full:
                try:
                    subscriber.get_nowait()
                except queue.Empty:
                    pass
                try:
                    subscriber.put_nowait(event)
                except queue.Full:
                    pass

    def state_snapshot(self):
        with self._state_lock:
            snapshot = dict(self._state)
            snapshot["messages"] = list(self.messages)
            snapshot["events"] = list(self.events)
            snapshot["session_token"] = self.session_token
        return snapshot

    def subscribe(self):
        subscriber = queue.Queue(maxsize=200)
        with self._subscriber_lock:
            self._subscribers.add(subscriber)
        return subscriber

    def unsubscribe(self, subscriber):
        with self._subscriber_lock:
            self._subscribers.discard(subscriber)

    def start(self):
        if not self.static_dir.joinpath("index.html").is_file():
            raise FileNotFoundError(
                f"Dashboard assets were not found in {self.static_dir}"
            )
        if self._server:
            return

        handler = self._handler_class()
        candidates = (
            [0]
            if self.requested_port == 0
            else list(range(self.requested_port, self.requested_port + 10))
        )
        last_error = None
        for candidate in candidates:
            try:
                self._server = ThreadingHTTPServer(
                    (self.host, candidate),
                    handler,
                )
                break
            except OSError as exc:
                last_error = exc
        if not self._server:
            raise OSError(
                f"Could not start the local dashboard: {last_error}"
            )

        server = self._server
        server.daemon_threads = True
        port = server.server_address[1]
        dashboard_url = f"http://{self.host}:{port}"
        with self._state_lock:
            self._state["url"] = dashboard_url
            self._state["status"] = "Ready"
            self._state["brain_state"] = "idle"
        self._started.set()
        self.emit_event(
            "system_online",
            {"url": dashboard_url, "local_only": True},
        )
        logging.info("JARVIS dashboard available at %s", dashboard_url)
        print(f"JARVIS dashboard: {dashboard_url}", flush=True)

        if self.open_browser and not os.environ.get("JARVIS_NO_BROWSER"):
            try:
                webbrowser.open(dashboard_url)
            except Exception as exc:
                logging.warning("Could not open dashboard browser: %s", exc)

        try:
            server.serve_forever(poll_interval=0.2)
        finally:
            self._stopped.set()

    def start_background(self, timeout=5):
        if self._server_thread and self._server_thread.is_alive():
            return
        self._server_thread = threading.Thread(
            target=self.start,
            daemon=True,
            name="jarvis-dashboard",
        )
        self._server_thread.start()
        if not self._started.wait(timeout):
            raise TimeoutError("The dashboard did not start in time.")

    def stop(self):
        server, self._server = self._server, None
        if server:
            try:
                server.shutdown()
            finally:
                server.server_close()
        self._stopped.set()

    def _dispatch(self, text):
        callback = self.callback_handler
        if not callback:
            return False
        threading.Thread(
            target=callback,
            args=(text,),
            daemon=True,
            name="jarvis-dashboard-command",
        ).start()
        return True

    def _origin_allowed(self, origin):
        if not origin:
            return True
        return origin in {
            self.url,
            self.url.replace("127.0.0.1", "localhost") if self.url else "",
        }

    def _handler_class(self):
        dashboard = self

        class DashboardRequestHandler(BaseHTTPRequestHandler):
            server_version = "JARVISDashboard/1.0"

            def log_message(self, message, *args):
                logging.debug("Dashboard: " + message, *args)

            def do_GET(self):
                path = urlparse(self.path).path
                if path == "/api/state":
                    self._send_json(dashboard.state_snapshot())
                    return
                if path == "/api/events":
                    self._serve_events()
                    return
                if path == "/api/health":
                    self._send_json(
                        {
                            "status": "ok",
                            "local_only": True,
                            "brain_state": dashboard.state_snapshot()[
                                "brain_state"
                            ],
                        }
                    )
                    return
                if path == "/favicon.ico":
                    self.send_response(HTTPStatus.NO_CONTENT)
                    self.end_headers()
                    return
                assets = {
                    "/": "index.html",
                    "/index.html": "index.html",
                    "/styles.css": "styles.css",
                    "/app.js": "app.js",
                }
                filename = assets.get(path)
                if not filename:
                    self.send_error(HTTPStatus.NOT_FOUND)
                    return
                self._send_asset(dashboard.static_dir / filename)

            def do_POST(self):
                path = urlparse(self.path).path
                if path not in {
                    "/api/message",
                    "/api/action",
                    "/api/mission",
                }:
                    self.send_error(HTTPStatus.NOT_FOUND)
                    return
                if not dashboard._origin_allowed(self.headers.get("Origin")):
                    self.send_error(HTTPStatus.FORBIDDEN)
                    return
                if not secrets.compare_digest(
                    self.headers.get("X-Jarvis-Token", ""),
                    dashboard.session_token,
                ):
                    self.send_error(HTTPStatus.FORBIDDEN)
                    return
                try:
                    length = int(self.headers.get("Content-Length", "0"))
                except ValueError:
                    self.send_error(HTTPStatus.BAD_REQUEST)
                    return
                if length <= 0 or length > 65536:
                    self.send_error(HTTPStatus.BAD_REQUEST)
                    return
                try:
                    payload = json.loads(
                        self.rfile.read(length).decode("utf-8")
                    )
                except (UnicodeDecodeError, ValueError):
                    self.send_error(HTTPStatus.BAD_REQUEST)
                    return

                if path == "/api/message":
                    text = str(payload.get("text", "")).strip()
                    if not text or len(text) > 4000:
                        self.send_error(HTTPStatus.BAD_REQUEST)
                        return
                elif path == "/api/mission":
                    goal = str(payload.get("goal", "")).strip()
                    if not goal or len(goal) > 2000:
                        self.send_error(HTTPStatus.BAD_REQUEST)
                        return
                    text = f"Super Mission: {goal}"
                else:
                    action = str(payload.get("action", "")).strip().lower()
                    commands = {
                        "allow": "yes",
                        "deny": "no",
                        "cancel": "stop generating",
                        "voice_on": "start listening",
                        "voice_off": "stop listening",
                        "mission_pause": "pause mission",
                        "mission_resume": "resume mission",
                        "mission_cancel": "cancel mission",
                        "shutdown": "exit",
                    }
                    text = commands.get(action)
                    if not text:
                        self.send_error(HTTPStatus.BAD_REQUEST)
                        return

                if not dashboard._dispatch(text):
                    self.send_error(
                        HTTPStatus.SERVICE_UNAVAILABLE,
                        "JARVIS is not ready.",
                    )
                    return
                self._send_json({"accepted": True}, status=HTTPStatus.ACCEPTED)

            def _serve_events(self):
                subscriber = dashboard.subscribe()
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", "text/event-stream")
                self.send_header("Cache-Control", "no-cache, no-store")
                self.send_header("Connection", "keep-alive")
                self._security_headers()
                self.end_headers()
                try:
                    connected = {
                        "id": 0,
                        "type": "connected",
                        "timestamp": time.time(),
                        "data": {},
                    }
                    self._write_event(connected)
                    while not dashboard._stopped.is_set():
                        try:
                            event = subscriber.get(timeout=15)
                            self._write_event(event)
                        except queue.Empty:
                            self.wfile.write(b": keep-alive\n\n")
                            self.wfile.flush()
                except (BrokenPipeError, ConnectionResetError, OSError):
                    pass
                finally:
                    dashboard.unsubscribe(subscriber)

            def _write_event(self, event):
                payload = json.dumps(
                    event,
                    ensure_ascii=False,
                    separators=(",", ":"),
                ).replace("\n", "\\n")
                self.wfile.write(f"id: {event['id']}\n".encode("utf-8"))
                self.wfile.write(
                    f"event: {event['type']}\n".encode("utf-8")
                )
                self.wfile.write(f"data: {payload}\n\n".encode("utf-8"))
                self.wfile.flush()

            def _send_asset(self, path):
                try:
                    content = path.read_bytes()
                except OSError:
                    self.send_error(HTTPStatus.NOT_FOUND)
                    return
                content_type = (
                    mimetypes.guess_type(str(path))[0]
                    or "application/octet-stream"
                )
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(len(content)))
                self.send_header("Cache-Control", "no-cache")
                self._security_headers()
                self.end_headers()
                self.wfile.write(content)

            def _send_json(self, payload, status=HTTPStatus.OK):
                content = json.dumps(
                    payload,
                    ensure_ascii=False,
                    separators=(",", ":"),
                ).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(content)))
                self.send_header("Cache-Control", "no-store")
                self._security_headers()
                self.end_headers()
                self.wfile.write(content)

            def _security_headers(self):
                self.send_header("X-Content-Type-Options", "nosniff")
                self.send_header("X-Frame-Options", "DENY")
                self.send_header("Referrer-Policy", "no-referrer")
                self.send_header(
                    "Content-Security-Policy",
                    "default-src 'self'; script-src 'self'; style-src 'self'; "
                    "connect-src 'self'; img-src 'self' data:; "
                    "font-src 'self'; object-src 'none'; frame-ancestors 'none'; "
                    "base-uri 'none'; form-action 'self'",
                )

        return DashboardRequestHandler

    @staticmethod
    def _brain_state_for_status(status):
        lower = status.lower()
        if not lower:
            return "idle"
        if "permission" in lower or "waiting" in lower:
            return "approval"
        if "cancel" in lower:
            return "cancelling"
        if "think" in lower or "continu" in lower:
            return "planning"
        if "listen" in lower:
            return "listening"
        if "respond" in lower or "stream" in lower:
            return "responding"
        return "working"
