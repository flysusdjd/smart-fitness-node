from __future__ import annotations

import importlib
import socket
import sys
import threading
import traceback
import webbrowser
from pathlib import Path

import uvicorn

DEFAULT_HOST = "0.0.0.0"
DEFAULT_PORT = 8787
PORT_SCAN_LIMIT = 10


def _ensure_project_root_on_path() -> None:
    current_file = Path(__file__).resolve()
    project_root = current_file.parent.parent
    project_root_str = str(project_root)
    if project_root_str not in sys.path:
        sys.path.insert(0, project_root_str)


def _is_port_available(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind((host, port))
        except OSError:
            return False
    return True


def _choose_port(host: str, preferred_port: int, limit: int) -> int:
    for port in range(preferred_port, preferred_port + limit):
        if _is_port_available(host, port):
            return port
    raise RuntimeError(
        f"没有找到可用端口，请先关闭 {preferred_port}-{preferred_port + limit - 1} 之间占用端口的程序后再试。"
    )


def _detect_lan_ip() -> str:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("8.8.8.8", 80))
            ip = sock.getsockname()[0]
            if ip and ip != "127.0.0.1":
                return ip
    except OSError:
        pass
    return "127.0.0.1"


def _check_app_importable() -> None:
    importlib.import_module("pc_gateway.api")


def _open_browser_later(url: str) -> None:
    timer = threading.Timer(1.0, lambda: webbrowser.open(url))
    timer.daemon = True
    timer.start()


def main() -> None:
    _ensure_project_root_on_path()
    port = _choose_port(DEFAULT_HOST, DEFAULT_PORT, PORT_SCAN_LIMIT)
    local_url = f"http://127.0.0.1:{port}/login"
    lan_ip = _detect_lan_ip()
    lan_url = f"http://{lan_ip}:{port}/login"

    if port != DEFAULT_PORT:
        print(f"端口 {DEFAULT_PORT} 已被占用，已自动切换到 {port}。")

    try:
        _check_app_importable()
    except Exception as exc:
        print("PC 网关启动失败：应用导入检查未通过。")
        print(f"错误原因：{exc}")
        print("请优先检查 pc_gateway 目录下的 Python 文件是否存在语法或配置错误。")
        traceback.print_exc()
        raise SystemExit(1) from exc

    print(f"本机访问地址：{local_url}")
    if lan_ip != "127.0.0.1":
        print(f"手机访问地址：{lan_url}")
    _open_browser_later(local_url)

    try:
        uvicorn.run(
            "pc_gateway.api:app",
            host=DEFAULT_HOST,
            port=port,
            reload=False,
        )
    except Exception as exc:
        print("PC 网关运行失败。")
        print(f"错误原因：{exc}")
        traceback.print_exc()
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
