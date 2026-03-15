#!/usr/bin/env -S uv run
"""Minimal request logging system."""

import json
import socket
import sqlite3
import subprocess
import time
from pathlib import Path
from typing import Any

from flask import Flask, Response, g, request

try:
    GIT_HASH = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, timeout=5).stdout.strip() or "unknown"
except Exception:  # noqa: BLE001
    GIT_HASH = "unknown"

CREATE_TABLE_QUERY = """
CREATE TABLE IF NOT EXISTS requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp REAL DEFAULT CURRENT_TIMESTAMP,
    method TEXT NOT NULL,
    path TEXT NOT NULL,
    metadata TEXT NOT NULL,
    processing_time REAL NOT NULL,
    ip_address TEXT,
    user_agent TEXT,
    referrer TEXT,
    is_secure BOOLEAN,
    status_code INTEGER,
    server_name TEXT,
    git_hash TEXT
)
"""


def setup_logging(app: Flask, db_path: Path):
    """Setup automatic request logging middleware."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        conn.execute(CREATE_TABLE_QUERY)
    conn.close()

    @app.before_request
    def before_request():
        """Initialize request metadata and timing."""
        g.request_metadata = {}
        g.request_start_time = time.perf_counter()

    @app.after_request
    def after_request(response: Response):
        """Log the completed request."""
        processing_time = time.perf_counter() - g.request_start_time
        try:
            log(
                db_path=db_path,
                method=request.method,
                path=request.path,
                metadata=g.request_metadata,
                processing_time=processing_time,
                ip_address=request.remote_addr,
                user_agent=request.user_agent.string if request.user_agent else None,
                referrer=request.referrer,
                is_secure=request.is_secure,
                status_code=response.status_code,
                server_name=socket.gethostname(),
                git_hash=GIT_HASH,
            )
        except Exception as e:  # noqa: BLE001
            app.logger.error(f"Failed to log request: {e}")
        return response


def log(
    db_path: Path,
    method: str,
    path: str,
    metadata: dict[str, Any],
    processing_time: float,
    ip_address: str | None,
    user_agent: str | None,
    referrer: str,
    is_secure: bool,
    status_code: int,
    server_name: str,
    git_hash: str,
):
    """Log a request to the database with git hash."""
    query = """INSERT INTO requests (
    method, path, metadata, processing_time, ip_address, user_agent, referrer, is_secure, status_code, server_name, git_hash
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"""
    params = (
        method,
        path,
        json.dumps(metadata),
        processing_time,
        ip_address,
        user_agent,
        referrer,
        is_secure,
        status_code,
        server_name,
        git_hash,
    )
    with sqlite3.connect(db_path) as conn:
        conn.execute(query, params)
    conn.close()
