#!/usr/bin/env python3
"""
Entrypoint for the KIRA backend container.

Responsibilities:
- Ensure runtime-mounted directories are writable by the runtime user (UID 1001).
- If directories are present (bind-mounted), recursively chown them to UID/GID 1001.
- Drop privileges to UID/GID 1001 and exec the final command.

This avoids requiring the container to be started as root in production while still
allowing safe ownership fixes for bind-mounted host directories.
"""
import os
import sys
import stat


TARGET_UID = 1001
TARGET_GID = 1001
TARGET_DIRS = ["/app/logs", "/app/audit"]


def safe_chown(path, uid, gid):
    try:
        for root, dirs, files in os.walk(path):
            try:
                os.chown(root, uid, gid)
            except Exception:
                pass
            for d in dirs:
                try:
                    os.chown(os.path.join(root, d), uid, gid)
                except Exception:
                    pass
            for f in files:
                try:
                    os.chown(os.path.join(root, f), uid, gid)
                except Exception:
                    pass
    except Exception:
        # Best-effort: ignore failures (mounted dirs may be read-only)
        return


def main():
    # If we're running as root, attempt to chown target directories when they exist
    euid = os.geteuid()
    if euid == 0:
        for d in TARGET_DIRS:
            if os.path.exists(d):
                try:
                    # ensure directory exists
                    os.makedirs(d, exist_ok=True)
                except Exception:
                    pass
                try:
                    os.chown(d, TARGET_UID, TARGET_GID)
                except Exception:
                    pass
                safe_chown(d, TARGET_UID, TARGET_GID)

    # Prepare command to exec
    cmd = sys.argv[1:]
    if not cmd:
        # Default to gunicorn command used historically
        cmd = [
            "gunicorn",
            "--bind",
            "0.0.0.0:5000",
            "--workers",
            "4",
            "--worker-class",
            "sync",
            "--timeout",
            "120",
            "--log-level",
            "info",
            "--access-logfile",
            "-",
            "--error-logfile",
            "-",
            "main:create_app()",
        ]

    # Drop privileges if running as root
    try:
        if os.geteuid() == 0:
            os.setgid(TARGET_GID)
            os.setuid(TARGET_UID)
    except Exception:
        # If dropping privileges fails, continue — the process will run as-is
        pass

    # Exec the final command (replacing PID 1)
    os.execvp(cmd[0], cmd)


if __name__ == "__main__":
    main()
