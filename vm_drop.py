"""
VM Drop — Ana PC <-> Sanal PC dosya aktarımı
VMware Tools kopyala-yapıştır / sürükle-bırak kapalıyken bile çalışır (ağ üzerinden).

Ana PC: dosyayı pencereye veya Outbox klasörüne bırak
Sanal:  otomatik indirir (Inbox)
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import socket
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox

# ── Görünüm ──────────────────────────────────────────────────────────────
BG, BG2, BG3 = "#0b1220", "#121a2b", "#1a2438"
TEXT, TEXT_DIM, ACCENT = "#e8eefc", "#93a4c3", "#3b82f6"
OK, WARN = "#34d399", "#fbbf24"
PORT_DEFAULT = 17865
APP_DIR = Path(__file__).resolve().parent
OUTBOX = APP_DIR / "Outbox"
INBOX = APP_DIR / "Inbox"

try:
    import windnd  # type: ignore
    WINDND_OK = True
except Exception:
    WINDND_OK = False


def local_ips() -> list[str]:
    ips = []
    try:
        hostname = socket.gethostname()
        for info in socket.getaddrinfo(hostname, None, socket.AF_INET):
            ip = info[4][0]
            if not ip.startswith("127.") and ip not in ips:
                ips.append(ip)
    except Exception:
        pass
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        if ip not in ips:
            ips.insert(0, ip)
    except Exception:
        pass
    return ips or ["127.0.0.1"]


def file_meta(path: Path) -> dict:
    data = path.read_bytes()
    return {
        "name": path.name,
        "size": path.stat().st_size,
        "mtime": int(path.stat().st_mtime),
        "sha1": hashlib.sha1(data).hexdigest(),
    }


def ensure_dirs():
    OUTBOX.mkdir(parents=True, exist_ok=True)
    INBOX.mkdir(parents=True, exist_ok=True)


# ── Host HTTP ────────────────────────────────────────────────────────────
class HostState:
    def __init__(self):
        self.lock = threading.Lock()
        self.log_fn = print
        self.outbox = OUTBOX


def make_handler(state: HostState):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            state.log_fn(f"[HTTP] {self.address_string()} — {fmt % args}")

        def _json(self, code: int, obj):
            raw = json.dumps(obj, ensure_ascii=False).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(raw)

        def _bytes(self, code: int, data: bytes, ctype: str, filename: str | None = None):
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            if filename:
                q = urllib.parse.quote(filename)
                self.send_header("Content-Disposition", f"attachment; filename*=UTF-8''{q}")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(data)

        def do_OPTIONS(self):
            self.send_response(204)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "*")
            self.end_headers()

        def do_GET(self):
            parsed = urllib.parse.urlparse(self.path)
            path = parsed.path
            if path == "/ping":
                self._json(200, {"ok": True, "role": "host"})
                return
            if path == "/list":
                files = []
                with state.lock:
                    for f in sorted(state.outbox.iterdir()):
                        if f.is_file() and not f.name.startswith("."):
                            try:
                                files.append(file_meta(f))
                            except Exception as e:
                                state.log_fn(f"list hata: {f.name}: {e}")
                self._json(200, {"files": files})
                return
            if path.startswith("/file/"):
                name = urllib.parse.unquote(path[len("/file/"):])
                name = Path(name).name
                target = state.outbox / name
                if not target.exists() or not target.is_file():
                    self._json(404, {"error": "not found"})
                    return
                self._bytes(200, target.read_bytes(), "application/octet-stream", name)
                return
            self._json(404, {"error": "unknown"})

        def do_POST(self):
            parsed = urllib.parse.urlparse(self.path)
            if parsed.path != "/upload":
                self._json(404, {"error": "unknown"})
                return
            length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(length)
            name = self.headers.get("X-Filename") or "upload.bin"
            name = Path(urllib.parse.unquote(name)).name
            dest = INBOX / name
            n = 1
            while dest.exists():
                dest = INBOX / f"{dest.stem}_{n}{dest.suffix}"
                n += 1
            dest.write_bytes(raw)
            state.log_fn(f"Sanaldan geldi: {dest.name} ({len(raw)} byte)")
            self._json(200, {"ok": True, "saved": dest.name})

    return Handler


# ── Uygulama ─────────────────────────────────────────────────────────────
class App:
    def __init__(self, root: tk.Tk):
        ensure_dirs()
        self.root = root
        self.root.title("VM Drop — Dosya Aktarım")
        self.root.configure(bg=BG)
        self.root.geometry("720x560")
        self.root.minsize(640, 480)

        self.mode = tk.StringVar(value="host")
        self.port = tk.StringVar(value=str(PORT_DEFAULT))
        self.host_ip = tk.StringVar(value="")
        self.status = tk.StringVar(value="Hazır")
        self.auto = tk.BooleanVar(value=True)

        self._server: ThreadingHTTPServer | None = None
        self._server_thread: threading.Thread | None = None
        self._poll_alive = False
        self._seen: dict[str, str] = {}
        self._host_state = HostState()
        self._host_state.log_fn = self.log

        self._build()
        self._set_mode_ui()
        if WINDND_OK:
            try:
                windnd.hook_dropfiles(self.root, self._on_drop_files)
            except Exception:
                pass

    def _build(self):
        top = tk.Frame(self.root, bg=BG2, pady=10, padx=12)
        top.pack(fill="x")
        tk.Label(top, text="VM Drop", bg=BG2, fg=TEXT,
                 font=("Segoe UI", 16, "bold")).pack(side="left")
        tk.Label(top, text="Ağ üzerinden sürükle-bırak aktarım",
                 bg=BG2, fg=TEXT_DIM, font=("Segoe UI", 10)).pack(side="left", padx=12)

        mode = tk.Frame(self.root, bg=BG, padx=12, pady=8)
        mode.pack(fill="x")
        tk.Label(mode, text="Bu bilgisayar:", bg=BG, fg=TEXT_DIM,
                 font=("Segoe UI", 10)).pack(side="left")
        tk.Radiobutton(mode, text="Ana PC (gönderen)", variable=self.mode, value="host",
                       bg=BG, fg=TEXT, selectcolor=BG3, activebackground=BG,
                       font=("Segoe UI", 10, "bold"),
                       command=self._set_mode_ui).pack(side="left", padx=8)
        tk.Radiobutton(mode, text="Sanal PC (alan)", variable=self.mode, value="guest",
                       bg=BG, fg=TEXT, selectcolor=BG3, activebackground=BG,
                       font=("Segoe UI", 10, "bold"),
                       command=self._set_mode_ui).pack(side="left", padx=8)

        self.cfg = tk.Frame(self.root, bg=BG3, padx=12, pady=10)
        self.cfg.pack(fill="x", padx=12)

        self.host_cfg = tk.Frame(self.cfg, bg=BG3)
        tk.Label(self.host_cfg, text="Port:", bg=BG3, fg=TEXT_DIM,
                 font=("Segoe UI", 10)).pack(side="left")
        tk.Entry(self.host_cfg, textvariable=self.port, width=8,
                 bg=BG2, fg=OK, font=("Consolas", 11, "bold"),
                 justify="center").pack(side="left", padx=6)
        self.ip_lbl = tk.Label(self.host_cfg, text="", bg=BG3, fg=ACCENT,
                               font=("Consolas", 10, "bold"))
        self.ip_lbl.pack(side="left", padx=10)
        self.btn_host = tk.Button(self.host_cfg, text="Sunucuyu Başlat",
                                  command=self.toggle_host,
                                  bg=ACCENT, fg="white", relief="flat",
                                  font=("Segoe UI", 10, "bold"), padx=12, pady=4,
                                  cursor="hand2")
        self.btn_host.pack(side="right")

        self.guest_cfg = tk.Frame(self.cfg, bg=BG3)
        tk.Label(self.guest_cfg, text="Ana PC IP:", bg=BG3, fg=TEXT_DIM,
                 font=("Segoe UI", 10)).pack(side="left")
        tk.Entry(self.guest_cfg, textvariable=self.host_ip, width=16,
                 bg=BG2, fg=OK, font=("Consolas", 11, "bold"),
                 justify="center").pack(side="left", padx=6)
        tk.Label(self.guest_cfg, text="Port:", bg=BG3, fg=TEXT_DIM,
                 font=("Segoe UI", 10)).pack(side="left")
        tk.Entry(self.guest_cfg, textvariable=self.port, width=7,
                 bg=BG2, fg=OK, font=("Consolas", 11, "bold"),
                 justify="center").pack(side="left", padx=6)
        tk.Checkbutton(self.guest_cfg, text="Otomatik al", variable=self.auto,
                       bg=BG3, fg=TEXT, selectcolor=BG2, activebackground=BG3,
                       font=("Segoe UI", 10)).pack(side="left", padx=8)
        self.btn_guest = tk.Button(self.guest_cfg, text="Bağlan / Al",
                                   command=self.toggle_guest,
                                   bg=OK, fg="#042f1a", relief="flat",
                                   font=("Segoe UI", 10, "bold"), padx=12, pady=4,
                                   cursor="hand2")
        self.btn_guest.pack(side="right")

        # Drop zone
        self.drop = tk.Frame(self.root, bg=BG2, highlightthickness=2,
                             highlightbackground=ACCENT, height=140)
        self.drop.pack(fill="x", padx=12, pady=12)
        self.drop.pack_propagate(False)
        self.drop_lbl = tk.Label(
            self.drop,
            text="Dosyaları buraya sürükleyip bırak\nveya aşağıdaki butonları kullan",
            bg=BG2, fg=TEXT, font=("Segoe UI", 13, "bold"), justify="center"
        )
        self.drop_lbl.pack(expand=True)

        btns = tk.Frame(self.root, bg=BG, padx=12)
        btns.pack(fill="x")
        tk.Button(btns, text="Dosya seç", command=self.pick_files,
                  bg=BG3, fg=TEXT, relief="flat", font=("Segoe UI", 10),
                  padx=10, pady=4, cursor="hand2").pack(side="left")
        tk.Button(btns, text="Outbox klasörünü aç", command=lambda: os.startfile(OUTBOX),
                  bg=BG3, fg=TEXT, relief="flat", font=("Segoe UI", 10),
                  padx=10, pady=4, cursor="hand2").pack(side="left", padx=6)
        tk.Button(btns, text="Inbox klasörünü aç", command=lambda: os.startfile(INBOX),
                  bg=BG3, fg=TEXT, relief="flat", font=("Segoe UI", 10),
                  padx=10, pady=4, cursor="hand2").pack(side="left")
        tk.Button(btns, text="Sanaldan Ana PC'ye gönder", command=self.send_to_host,
                  bg=BG3, fg=WARN, relief="flat", font=("Segoe UI", 10),
                  padx=10, pady=4, cursor="hand2").pack(side="right")

        tk.Label(self.root, textvariable=self.status, bg=BG, fg=OK,
                 font=("Segoe UI", 10, "bold"), anchor="w",
                 padx=14).pack(fill="x", pady=(8, 0))

        log_fr = tk.Frame(self.root, bg=BG, padx=12, pady=8)
        log_fr.pack(fill="both", expand=True)
        self.log_box = tk.Text(log_fr, bg="#070d18", fg=TEXT_DIM,
                               font=("Consolas", 10), relief="flat",
                               wrap="word", height=12)
        self.log_box.pack(fill="both", expand=True)
        self.log_box.configure(state="disabled")

        tip = ("İpucu: VMware'de sanal ağ Bridged veya Host-only olsun. "
               "Firewall ilk seferde Python'a izin verin.")
        if not WINDND_OK:
            tip += "  |  Daha iyi sürükle-bırak için: pip install windnd"
        tk.Label(self.root, text=tip, bg=BG, fg=TEXT_DIM,
                 font=("Segoe UI", 8), anchor="w", padx=12, pady=6).pack(fill="x")

        self.log("Outbox: " + str(OUTBOX))
        self.log("Inbox : " + str(INBOX))
        if WINDND_OK:
            self.log("Sürükle-bırak aktif (windnd).")
        else:
            self.log("windnd yok — Outbox klasörüne dosya atarak da gönderebilirsin.")

    def _set_mode_ui(self):
        for w in self.host_cfg.winfo_children():
            pass
        self.host_cfg.pack_forget()
        self.guest_cfg.pack_forget()
        if self.mode.get() == "host":
            self.host_cfg.pack(fill="x")
            ips = ", ".join(local_ips())
            self.ip_lbl.configure(text=f"Bu PC IP: {ips}")
            self.drop_lbl.configure(
                text="ANA PC MODU\nDosyayı buraya sürükle → sanal otomatik alır"
            )
        else:
            self.guest_cfg.pack(fill="x")
            self.drop_lbl.configure(
                text="SANAL PC MODU\nBağlan'a bas → Ana PC'deki dosyalar Inbox'a iner\n"
                     "(İstersen buraya da dosya bırakıp Ana PC'ye gönderebilirsin)"
            )

    def log(self, msg: str):
        line = time.strftime("%H:%M:%S") + "  " + msg

        def ui():
            self.log_box.configure(state="normal")
            self.log_box.insert("end", line + "\n")
            self.log_box.see("end")
            self.log_box.configure(state="disabled")
            self.status.set(msg)

        if threading.current_thread() is threading.main_thread():
            ui()
        else:
            self.root.after(0, ui)

    # ── Drop / dosya ekleme (host outbox) ────────────────────────────────
    def _on_drop_files(self, files):
        paths = []
        for f in files:
            if isinstance(f, bytes):
                f = f.decode("utf-8", errors="ignore")
            paths.append(Path(f))
        self.add_files(paths)

    def pick_files(self):
        files = filedialog.askopenfilenames(title="Gönderilecek dosyalar")
        if files:
            self.add_files([Path(f) for f in files])

    def add_files(self, paths: list[Path]):
        ensure_dirs()
        if self.mode.get() == "guest":
            # guest'te drop = ana PC'ye upload kuyruğu için önce inbox'a değil, upload
            for src in paths:
                if src.is_file():
                    self._upload_file(src)
            return

        for src in paths:
            try:
                if not src.exists():
                    continue
                if src.is_dir():
                    self.log(f"Klasör atlandı (şimdilik sadece dosya): {src.name}")
                    continue
                dest = OUTBOX / src.name
                if src.resolve() == dest.resolve():
                    self.log(f"Zaten Outbox'ta: {src.name}")
                    continue
                shutil.copy2(src, dest)
                self.log(f"Outbox'a eklendi: {src.name}")
            except Exception as e:
                self.log(f"Eklenemedi: {src} — {e}")

    # ── Host server ──────────────────────────────────────────────────────
    def toggle_host(self):
        if self._server:
            self.stop_host()
        else:
            self.start_host()

    def start_host(self):
        ensure_dirs()
        try:
            port = int(self.port.get().strip())
        except ValueError:
            messagebox.showerror("Port", "Geçerli bir port gir.")
            return
        self._host_state.outbox = OUTBOX
        handler = make_handler(self._host_state)
        try:
            self._server = ThreadingHTTPServer(("0.0.0.0", port), handler)
        except OSError as e:
            messagebox.showerror("Sunucu", f"Port açılamadı: {e}")
            return
        self._server_thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._server_thread.start()
        self.btn_host.configure(text="Sunucuyu Durdur", bg="#d64545")
        ips = local_ips()
        self.log(f"Sunucu açık — port {port}")
        self.log(f"Sanalda Ana PC IP olarak şunu yaz: {ips[0]}")
        messagebox.showinfo(
            "Sunucu hazır",
            f"Ana PC sunucusu çalışıyor.\n\nSanal PC'de IP: {ips[0]}\nPort: {port}"
        )

    def stop_host(self):
        if self._server:
            try:
                self._server.shutdown()
            except Exception:
                pass
            self._server = None
        self.btn_host.configure(text="Sunucuyu Başlat", bg=ACCENT)
        self.log("Sunucu durdu.")

    # ── Guest poll ───────────────────────────────────────────────────────
    def toggle_guest(self):
        if self._poll_alive:
            self._poll_alive = False
            self.btn_guest.configure(text="Bağlan / Al", bg=OK, fg="#042f1a")
            self.log("Alma durdu.")
        else:
            if not self.host_ip.get().strip():
                messagebox.showerror("IP", "Ana PC IP adresini yaz.")
                return
            self._poll_alive = True
            self.btn_guest.configure(text="Durdur", bg="#d64545", fg="white")
            threading.Thread(target=self._guest_loop, daemon=True).start()
            self.log(f"Bağlanıyor: {self.host_ip.get().strip()}:{self.port.get()}")

    def _base_url(self) -> str:
        ip = self.host_ip.get().strip()
        port = self.port.get().strip()
        return f"http://{ip}:{port}"

    def _guest_loop(self):
        ensure_dirs()
        while self._poll_alive:
            try:
                url = self._base_url() + "/list"
                with urllib.request.urlopen(url, timeout=3) as r:
                    data = json.loads(r.read().decode("utf-8"))
                files = data.get("files", [])
                for meta in files:
                    key = meta["name"]
                    sig = f'{meta["sha1"]}:{meta["size"]}'
                    if self._seen.get(key) == sig:
                        continue
                    self._download_one(meta["name"])
                    self._seen[key] = sig
                if not self.auto.get():
                    break
            except Exception as e:
                self.log(f"Bağlantı: {e}")
            if not self.auto.get():
                break
            time.sleep(1.2)
        self._poll_alive = False
        self.root.after(0, lambda: self.btn_guest.configure(
            text="Bağlan / Al", bg=OK, fg="#042f1a"))

    def _download_one(self, name: str):
        ensure_dirs()
        q = urllib.parse.quote(name)
        url = self._base_url() + "/file/" + q
        dest = INBOX / name
        n = 1
        # aynı isimde farklı içerik gelirse üzerine yazma, yenisini kaydet
        tmp = dest
        while tmp.exists() and self._seen.get(name) and False:
            tmp = INBOX / f"{dest.stem}_{n}{dest.suffix}"
            n += 1
        try:
            with urllib.request.urlopen(url, timeout=60) as r:
                data = r.read()
            # aynı dosya varsa üzerine yaz (güncelleme)
            dest.write_bytes(data)
            self.log(f"İndirildi → Inbox\\{dest.name} ({len(data)} byte)")
        except Exception as e:
            self.log(f"İndirme hatası ({name}): {e}")

    def send_to_host(self):
        if self.mode.get() != "guest":
            messagebox.showinfo("Bilgi", "Bu buton Sanal PC modunda, dosyayı Ana PC'ye yollar.")
        files = filedialog.askopenfilenames(title="Ana PC'ye gönder")
        if not files:
            return
        for f in files:
            self._upload_file(Path(f))

    def _upload_file(self, src: Path):
        if not self.host_ip.get().strip():
            messagebox.showerror("IP", "Önce Ana PC IP yaz.")
            return
        try:
            data = src.read_bytes()
            req = urllib.request.Request(
                self._base_url() + "/upload",
                data=data,
                method="POST",
                headers={
                    "Content-Type": "application/octet-stream",
                    "X-Filename": urllib.parse.quote(src.name),
                },
            )
            with urllib.request.urlopen(req, timeout=120) as r:
                resp = json.loads(r.read().decode("utf-8"))
            self.log(f"Ana PC'ye gönderildi: {src.name} → {resp.get('saved')}")
        except Exception as e:
            self.log(f"Gönderim hatası: {e}")

    def on_close(self):
        self._poll_alive = False
        self.stop_host()
        self.root.destroy()


def main():
    ensure_dirs()
    root = tk.Tk()
    try:
        root.tk.call("tk", "scaling", 1.2)
    except Exception:
        pass
    app = App(root)
    root.protocol("WM_DELETE_WINDOW", app.on_close)
    root.mainloop()


if __name__ == "__main__":
    main()
