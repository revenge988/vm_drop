"""
VM Drop Host — Ana PC'de çalışır.
VMware penceresinin üstüne yapışan bırakma çubuğu:
dosyayı oraya sürükle-bırak → ilgili sanalın Masaüstü'ne gider.
"""
from __future__ import annotations

import json
import socket
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
import ctypes
from ctypes import wintypes
import tkinter as tk
from tkinter import messagebox, simpledialog

APP_DIR = Path(__file__).resolve().parent
CFG_PATH = APP_DIR / "host_config.json"
DISCOVER_PORT = 17866
BAR_H = 42

user32 = ctypes.windll.user32
EnumWindows = user32.EnumWindows
EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
GetWindowTextW = user32.GetWindowTextW
GetWindowTextLengthW = user32.GetWindowTextLengthW
IsWindowVisible = user32.IsWindowVisible
GetWindowRect = user32.GetWindowRect

try:
    import windnd  # type: ignore
    WINDND_OK = True
except Exception:
    WINDND_OK = False


class RECT(ctypes.Structure):
    _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long),
                ("right", ctypes.c_long), ("bottom", ctypes.c_long)]


def window_title(hwnd) -> str:
    n = GetWindowTextLengthW(hwnd)
    if n <= 0:
        return ""
    buf = ctypes.create_unicode_buffer(n + 1)
    GetWindowTextW(hwnd, buf, n + 1)
    return buf.value


def window_rect(hwnd):
    r = RECT()
    if not GetWindowRect(hwnd, ctypes.byref(r)):
        return None
    return r.left, r.top, r.right, r.bottom


def find_vmware_windows() -> list[tuple[int, str]]:
    found = []

    def cb(hwnd, _lp):
        if not IsWindowVisible(hwnd):
            return True
        title = window_title(hwnd)
        if "VMware Workstation" in title or "VMware Workstation Pro" in title:
            # Örn: "PC-2 - VMware Workstation"
            found.append((int(hwnd), title))
        return True

    EnumWindows(EnumWindowsProc(cb), 0)
    return found


def guess_vm_name(title: str) -> str:
    # "PC-2 - VMware Workstation" -> PC-2
    if " - " in title:
        return title.split(" - ", 1)[0].strip()
    return title.strip()


def load_cfg() -> dict:
    if CFG_PATH.exists():
        try:
            return json.loads(CFG_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"targets": {}, "port": 17865}


def save_cfg(cfg: dict):
    CFG_PATH.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")


def send_file(ip: str, port: int, path: Path) -> str:
    data = path.read_bytes()
    req = urllib.request.Request(
        f"http://{ip}:{port}/drop",
        data=data,
        method="POST",
        headers={
            "Content-Type": "application/octet-stream",
            "X-Filename": urllib.parse.quote(path.name),
        },
    )
    with urllib.request.urlopen(req, timeout=180) as r:
        resp = json.loads(r.read().decode("utf-8"))
    if not resp.get("ok"):
        raise RuntimeError(resp.get("error", "unknown"))
    return resp.get("saved", path.name)


class DropBar(tk.Toplevel):
    def __init__(self, master, hwnd: int, title: str, app: "HostApp"):
        super().__init__(master)
        self.hwnd = hwnd
        self.vm_title = title
        self.vm_name = guess_vm_name(title)
        self.app = app

        self.overrideredirect(True)
        self.attributes("-topmost", True)
        self.configure(bg="#1d4ed8")

        self.lbl = tk.Label(
            self,
            text=f"⬇  {self.vm_name} — dosyayı BURAYA bırak (Masaüstü'ne gider)",
            bg="#1d4ed8", fg="white",
            font=("Segoe UI", 11, "bold"),
            padx=8,
        )
        self.lbl.pack(fill="both", expand=True)

        if WINDND_OK:
            try:
                windnd.hook_dropfiles(self, self._on_drop)
            except Exception:
                pass

        self.bind("<Button-3>", self._ask_ip)  # sağ tık = IP ayarla
        self.lbl.bind("<Button-3>", self._ask_ip)

    def _on_drop(self, files):
        paths = []
        for f in files:
            if isinstance(f, bytes):
                f = f.decode("utf-8", errors="ignore")
            p = Path(f)
            if p.is_file():
                paths.append(p)
        if paths:
            self.app.handle_drop(self.vm_name, paths, self)

    def _ask_ip(self, _e=None):
        self.app.ask_ip_for(self.vm_name)

    def flash(self, ok: bool):
        color = "#059669" if ok else "#dc2626"
        self.configure(bg=color)
        self.lbl.configure(bg=color)
        self.after(900, lambda: (self.configure(bg="#1d4ed8"), self.lbl.configure(bg="#1d4ed8")))

    def follow(self):
        rect = window_rect(self.hwnd)
        if not rect:
            self.withdraw()
            return
        l, t, r, b = rect
        w = max(200, r - l)
        # VMware başlık/menü altına yapışık şerit
        y = t + 70
        self.geometry(f"{w}x{BAR_H}+{l}+{y}")
        try:
            self.deiconify()
        except Exception:
            pass


class HostApp:
    def __init__(self):
        self.cfg = load_cfg()
        self.root = tk.Tk()
        self.root.title("VM Drop Host — Ana PC")
        self.root.geometry("520x380")
        self.root.configure(bg="#0b1220")

        self.status = tk.StringVar(value="VMware pencereleri aranıyor...")
        self.discovered: dict[str, str] = {}  # name -> ip
        self.bars: dict[int, DropBar] = {}

        tk.Label(self.root, text="VM Drop Host", bg="#0b1220", fg="#e8eefc",
                 font=("Segoe UI", 16, "bold")).pack(pady=(12, 2))
        tk.Label(
            self.root,
            text="VMware penceresinin üstündeki mavi şeride dosya bırak.\n"
                 "Her sanalda guest_agent.py açık olmalı.\n"
                 "Şeride sağ tık = o sanalın IP'sini ayarla.",
            bg="#0b1220", fg="#93a4c3", font=("Segoe UI", 9), justify="center"
        ).pack()

        if not WINDND_OK:
            tk.Label(self.root, text="⚠ windnd yok — pip install windnd",
                     bg="#0b1220", fg="#fbbf24", font=("Segoe UI", 9, "bold")).pack()

        self.listbox = tk.Listbox(self.root, bg="#121a2b", fg="#e8eefc",
                                  font=("Consolas", 10), height=10,
                                  selectbackground="#1d4ed8")
        self.listbox.pack(fill="both", expand=True, padx=14, pady=10)

        btn = tk.Frame(self.root, bg="#0b1220")
        btn.pack(fill="x", padx=14, pady=(0, 8))
        tk.Button(btn, text="IP eşlemesini düzenle", command=self.edit_mapping,
                  bg="#1a2438", fg="white", relief="flat",
                  font=("Segoe UI", 9), padx=8, pady=4, cursor="hand2").pack(side="left")
        tk.Button(btn, text="Yenile", command=self.refresh_list,
                  bg="#1a2438", fg="white", relief="flat",
                  font=("Segoe UI", 9), padx=8, pady=4, cursor="hand2").pack(side="left", padx=6)

        tk.Label(self.root, textvariable=self.status, bg="#0b1220", fg="#34d399",
                 font=("Segoe UI", 9, "bold"), anchor="w").pack(fill="x", padx=14, pady=(0, 10))

        threading.Thread(target=self._discover_loop, daemon=True).start()
        self.root.after(400, self._tick)
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def _discover_loop(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind(("", DISCOVER_PORT))
        except OSError:
            return
        sock.settimeout(1.0)
        while True:
            try:
                data, addr = sock.recvfrom(256)
                msg = data.decode("utf-8", errors="ignore")
                # VMDROP|PC-2|17865
                if msg.startswith("VMDROP|"):
                    parts = msg.split("|")
                    if len(parts) >= 3:
                        name = parts[1].strip()
                        self.discovered[name] = addr[0]
                        # config'e otomatik yaz (yoksa)
                        targets = self.cfg.setdefault("targets", {})
                        if name not in targets or not targets[name]:
                            targets[name] = addr[0]
                            save_cfg(self.cfg)
            except socket.timeout:
                continue
            except Exception:
                time.sleep(0.5)

    def resolve_ip(self, vm_name: str) -> str | None:
        targets = self.cfg.get("targets", {})
        ip = targets.get(vm_name) or self.discovered.get(vm_name)
        return ip

    def ask_ip_for(self, vm_name: str):
        cur = self.resolve_ip(vm_name) or ""
        ip = simpledialog.askstring(
            "Sanal IP",
            f"{vm_name} için sanalın IP adresini yaz\n(ör. 192.168.x.x):",
            initialvalue=cur,
            parent=self.root,
        )
        if ip:
            self.cfg.setdefault("targets", {})[vm_name] = ip.strip()
            save_cfg(self.cfg)
            self.status.set(f"{vm_name} → {ip.strip()}")
            self.refresh_list()

    def edit_mapping(self):
        # basit: seçili satırdan isim al
        names = sorted(set(
            [guess_vm_name(t) for _, t in find_vmware_windows()]
            + list(self.cfg.get("targets", {}).keys())
            + list(self.discovered.keys())
        ))
        if not names:
            messagebox.showinfo("IP", "Önce bir VMware penceresi aç.")
            return
        # ilk bulunanı sor — çoklu için sırayla
        for name in names:
            self.ask_ip_for(name)

    def refresh_list(self):
        self.listbox.delete(0, "end")
        vms = find_vmware_windows()
        if not vms:
            self.listbox.insert("end", "(Açık VMware penceresi yok)")
        for hwnd, title in vms:
            name = guess_vm_name(title)
            ip = self.resolve_ip(name) or "?"
            self.listbox.insert("end", f"{name:8}  IP={ip:15}  | {title}")
        for name, ip in sorted(self.discovered.items()):
            self.listbox.insert("end", f"[keşfedildi] {name} → {ip}")

    def handle_drop(self, vm_name: str, paths: list[Path], bar: DropBar):
        ip = self.resolve_ip(vm_name)
        if not ip:
            self.status.set(f"{vm_name} IP bilinmiyor — şeride sağ tıkla")
            bar.flash(False)
            self.ask_ip_for(vm_name)
            ip = self.resolve_ip(vm_name)
            if not ip:
                return
        port = int(self.cfg.get("port", 17865))

        def work():
            ok_all = True
            for p in paths:
                try:
                    self.root.after(0, lambda n=p.name: self.status.set(f"Gönderiliyor: {n} → {vm_name}"))
                    saved = send_file(ip, port, p)
                    self.root.after(0, lambda n=p.name, s=saved: self.status.set(f"OK: {n} → {s}"))
                except Exception as e:
                    ok_all = False
                    self.root.after(0, lambda err=str(e): self.status.set(f"Hata: {err}"))
            self.root.after(0, lambda: bar.flash(ok_all))

        threading.Thread(target=work, daemon=True).start()

    def _tick(self):
        vms = {hwnd: title for hwnd, title in find_vmware_windows()}
        # eski barları kapat
        for hwnd in list(self.bars.keys()):
            if hwnd not in vms:
                try:
                    self.bars[hwnd].destroy()
                except Exception:
                    pass
                del self.bars[hwnd]
        # yenileri ekle / takip et
        for hwnd, title in vms.items():
            if hwnd not in self.bars:
                self.bars[hwnd] = DropBar(self.root, hwnd, title, self)
            else:
                self.bars[hwnd].vm_title = title
                self.bars[hwnd].vm_name = guess_vm_name(title)
            self.bars[hwnd].follow()
        self.refresh_list()
        self.root.after(400, self._tick)

    def on_close(self):
        for bar in list(self.bars.values()):
            try:
                bar.destroy()
            except Exception:
                pass
        self.root.destroy()

    def run(self):
        self.root.mainloop()


def main():
    if not WINDND_OK:
        # yine aç, uyarı göster
        pass
    HostApp().run()


if __name__ == "__main__":
    main()
