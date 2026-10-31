"""
VM Drop Guest Agent — Sanal PC'de çalışır.
Ana PC'den gelen dosyaları Masaüstü'ne kaydeder.
restrict_backdoor=TRUE iken de çalışır (ağ üzerinden).
"""
from __future__ import annotations

import json
import socket
import threading
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import ctypes
import tkinter as tk
from tkinter import messagebox

from common import app_dir, default_gateway_guess, local_ipv4s, open_firewall_tcp

PORT = 17865
DISCOVER_PORT = 17866
APP_DIR = app_dir()
CFG = APP_DIR / "guest_config.json"


def desktop_dir() -> Path:
    buf = ctypes.create_unicode_buffer(260)
    ctypes.windll.shell32.SHGetFolderPathW(None, 0, None, 0, buf)
    p = Path(buf.value)
    if p.exists():
        return p
    alt = Path.home() / "Desktop"
    if alt.exists():
        return alt
    return Path.home() / "Masaüstü"


def load_cfg() -> dict:
    if CFG.exists():
        try:
            return json.loads(CFG.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"name": "PC-2", "port": PORT, "notify": True}


def save_cfg(d: dict):
    try:
        CFG.write_text(json.dumps(d, indent=2, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass


class Receiver:
    def __init__(self, name: str, port: int, notify_cb=None):
        self.name = name
        self.port = port
        self.notify_cb = notify_cb
        self.desktop = desktop_dir()
        self._httpd: ThreadingHTTPServer | None = None

    def start(self):
        open_firewall_tcp(self.port, "VM Drop Agent")
        handler = self._make_handler()
        self._httpd = ThreadingHTTPServer(("0.0.0.0", self.port), handler)
        threading.Thread(target=self._httpd.serve_forever, daemon=True).start()
        threading.Thread(target=self._broadcast_loop, daemon=True).start()

    def stop(self):
        if self._httpd:
            try:
                self._httpd.shutdown()
            except Exception:
                pass

    def _broadcast_loop(self):
        payload = f"VMDROP|{self.name}|{self.port}".encode("utf-8")
        while True:
            targets = {"255.255.255.255"}
            for ip in local_ipv4s():
                parts = ip.split(".")
                if len(parts) == 4:
                    targets.add(".".join(parts[:3] + ["255"]))
                    gw = default_gateway_guess(ip)
                    if gw:
                        targets.add(gw)
            for dest in targets:
                try:
                    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                    s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
                    s.sendto(payload, (dest, DISCOVER_PORT))
                    s.close()
                except Exception:
                    pass
            time.sleep(2.0)

    def _save(self, filename: str, data: bytes) -> Path:
        name = Path(filename).name or "dosya.bin"
        dest = self.desktop / name
        n = 1
        while dest.exists():
            dest = self.desktop / f"{Path(name).stem}_{n}{Path(name).suffix}"
            n += 1
        dest.write_bytes(data)
        return dest

    def _make_handler(self):
        recv = self

        class H(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def _json(self, code, obj):
                raw = json.dumps(obj, ensure_ascii=False).encode("utf-8")
                self.send_response(code)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(raw)))
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(raw)

            def do_OPTIONS(self):
                self.send_response(204)
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
                self.send_header("Access-Control-Allow-Headers", "*")
                self.end_headers()

            def do_GET(self):
                if self.path.startswith("/ping"):
                    self._json(200, {
                        "ok": True,
                        "name": recv.name,
                        "desktop": str(recv.desktop),
                        "ips": local_ipv4s(),
                    })
                    return
                self._json(404, {"error": "not found"})

            def do_POST(self):
                if self.path != "/drop":
                    self._json(404, {"error": "not found"})
                    return
                length = int(self.headers.get("Content-Length", "0"))
                data = self.rfile.read(length)
                raw_name = self.headers.get("X-Filename", "dosya.bin")
                name = urllib.parse.unquote(raw_name)
                try:
                    dest = recv._save(name, data)
                    if recv.notify_cb:
                        recv.notify_cb(dest.name, len(data))
                    self._json(200, {"ok": True, "saved": str(dest)})
                except Exception as e:
                    self._json(500, {"error": str(e)})

        return H


class GuestUI:
    def __init__(self):
        self.cfg = load_cfg()
        self.root = tk.Tk()
        self.root.title("VM Drop Agent (Sanal)")
        self.root.geometry("480x300")
        self.root.configure(bg="#0b1220")
        self.root.attributes("-topmost", True)

        self.name_var = tk.StringVar(value=self.cfg.get("name", "PC-2"))
        self.port_var = tk.StringVar(value=str(self.cfg.get("port", PORT)))
        self.status = tk.StringVar(value="Başlatılıyor...")
        self.ip_var = tk.StringVar(value="")

        tk.Label(self.root, text="Sanal PC Agent", bg="#0b1220", fg="#e8eefc",
                 font=("Segoe UI", 14, "bold")).pack(pady=(14, 4))
        tk.Label(
            self.root,
            text="Oyunda backdoor kapalı kalsın.\nBu program ağdan dosya alır → Masaüstü",
            bg="#0b1220", fg="#93a4c3", font=("Segoe UI", 9), justify="center",
        ).pack()

        fr = tk.Frame(self.root, bg="#121a2b")
        fr.pack(fill="x", padx=16, pady=12)
        tk.Label(fr, text="Sanal adı (PC-1/PC-2):", bg="#121a2b", fg="#93a4c3",
                 font=("Segoe UI", 9)).grid(row=0, column=0, sticky="w", padx=8, pady=6)
        tk.Entry(fr, textvariable=self.name_var, width=14, bg="#1a2438", fg="#34d399",
                 font=("Consolas", 11, "bold"), justify="center").grid(row=0, column=1, padx=8)
        tk.Label(fr, text="Port:", bg="#121a2b", fg="#93a4c3",
                 font=("Segoe UI", 9)).grid(row=1, column=0, sticky="w", padx=8, pady=6)
        tk.Entry(fr, textvariable=self.port_var, width=8, bg="#1a2438", fg="#34d399",
                 font=("Consolas", 11, "bold"), justify="center").grid(row=1, column=1, sticky="w", padx=8)

        tk.Label(self.root, textvariable=self.ip_var, bg="#0b1220", fg="#fbbf24",
                 font=("Consolas", 10, "bold")).pack()

        tk.Button(self.root, text="Kaydet & Dinle", command=self.restart,
                  bg="#3b82f6", fg="white", relief="flat",
                  font=("Segoe UI", 10, "bold"), padx=12, pady=6,
                  cursor="hand2").pack(pady=4)

        tk.Label(self.root, textvariable=self.status, bg="#0b1220", fg="#34d399",
                 font=("Segoe UI", 10, "bold")).pack(pady=8)

        self.agent: Receiver | None = None
        self.root.after(300, self.restart)
        self.root.protocol("WM_DELETE_WINDOW", self._hide)

    def _hide(self):
        self.root.withdraw()

    def notify(self, name: str, size: int):
        def ui():
            self.status.set(f"Alındı: {name} ({size} byte) → Masaüstü")
            try:
                self.root.deiconify()
                self.root.attributes("-topmost", True)
            except Exception:
                pass
        self.root.after(0, ui)

    def restart(self):
        if self.agent:
            self.agent.stop()
        try:
            port = int(self.port_var.get().strip())
        except ValueError:
            messagebox.showerror("Port", "Geçersiz port")
            return
        name = self.name_var.get().strip() or "PC-2"
        self.cfg = {"name": name, "port": port, "notify": True}
        save_cfg(self.cfg)
        self.agent = Receiver(name, port, notify_cb=self.notify)
        try:
            self.agent.start()
        except OSError as e:
            messagebox.showerror("Agent", f"Port açılamadı: {e}")
            return
        ips = ", ".join(local_ipv4s())
        self.ip_var.set(f"Bu sanalın IP'si: {ips}")
        desk = desktop_dir()
        self.status.set(f"Dinliyor: {name} :{port} → {desk}")

    def run(self):
        self.root.mainloop()


def main():
    GuestUI().run()


if __name__ == "__main__":
    main()
