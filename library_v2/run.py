from __future__ import annotations

import argparse
import os
import shutil
import socket
import subprocess
import sys
import webbrowser
from pathlib import Path

# Ensure library_v2 is importable regardless of current working directory
PACKAGE_ROOT = Path(__file__).resolve().parent
if str(PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_ROOT))

from library_app.config import AppConfig
from library_app.web.server import create_server

UNSAFE_BROWSER_PORTS = {6000, 6566, 6665, 6666, 6667, 6668, 6669, 6697, 10080}


def find_available_port(host: str, preferred_port: int) -> int:
    for candidate in [preferred_port, *range(preferred_port + 1, preferred_port + 50)]:
        if candidate in UNSAFE_BROWSER_PORTS:
            continue
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                sock.bind((host, candidate))
                return candidate
            except OSError:
                continue
    for _ in range(10):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.bind((host, 0))
            port = int(sock.getsockname()[1])
            if port not in UNSAFE_BROWSER_PORTS:
                return port
    return preferred_port


def launch_browser(url: str, mode: str = "app") -> None:
    if mode == "app" and os.name == "nt":
        edge_candidates = [
            Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
            Path(r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"),
            Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
        ]
        for exe in edge_candidates:
            if exe.exists():
                subprocess.Popen(
                    [str(exe), f"--app={url}", "--window-size=1360,860"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                return
        edge_in_path = shutil.which("msedge") or shutil.which("chrome")
        if edge_in_path:
            subprocess.Popen(
                [edge_in_path, f"--app={url}"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return
    webbrowser.open(url)


def main() -> None:
    parser = argparse.ArgumentParser(description="Library Manager v2 — Persian Library Studio")
    parser.add_argument("--data", type=Path, default=None, help="Path to Excel file (default: data/Books_v2.xlsx)")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8765, help="Port to listen on (default: 8765)")
    parser.add_argument("--no-browser", action="store_true", help="Do not open browser automatically")
    parser.add_argument("--browser-mode", choices=("app", "tab"), default="app", help="Open as standalone app window or browser tab")
    args = parser.parse_args()

    workspace_root = PACKAGE_ROOT.parent
    selected_port = find_available_port(args.host, args.port)
    config = AppConfig.from_workspace(
        workspace_root=workspace_root,
        excel_path=args.data,
        host=args.host,
        port=selected_port,
    )

    server, _ = create_server(config)
    url = f"http://{config.host}:{selected_port}/"
    print(f"Library Studio v2 running at {url}")
    print(f"Excel data source: {config.excel_path}")

    if not args.no_browser:
        launch_browser(url, mode=args.browser_mode)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down Library Studio v2...")
    finally:
        server.shutdown()
        server.server_close()


if __name__ == "__main__":
    main()
