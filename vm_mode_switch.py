"""
VM Mode Switch — Tek program.
Dosya Modu  = restrict_backdoor FALSE → VMware native sürükle-bırak açılır
Oyun Modu   = restrict_backdoor TRUE  → oyun genelde izin verir, DnD kapanır

VM KAPALI iken mod değiştir, sonra VM'yi aç.
"""
from __future__ import annotations

import re
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox

KEYS = (
    "monitor_control.restrict_backdoor",
    "monitor_control.disable_directexec",
)

DND_EXTRA = {
    "isolation.tools.dnd.disable": "FALSE",
    "isolation.tools.copy.enable": "TRUE",
    "isolation.tools.paste.enable": "TRUE",
}


def set_vmx_value(text: str, key: str, value: str) -> str:
    pat = re.compile(rf'(?m)^\s*{re.escape(key)}\s*=\s*".*?"\s*$')
    line = f'{key} = "{value}"'
    if pat.search(text):
        return pat.sub(line, text)
    # dosya sonuna ekle
    if not text.endswith("\n"):
        text += "\n"
    return text + line + "\n"


def apply_mode(vmx_path: Path, game_mode: bool) -> None:
    raw = vmx_path.read_text(encoding="utf-8", errors="ignore")
    val = "TRUE" if game_mode else "FALSE"
    for key in KEYS:
        raw = set_vmx_value(raw, key, val)
    if not game_mode:
        for k, v in DND_EXTRA.items():
            raw = set_vmx_value(raw, k, v)
    # yedek
    bak = vmx_path.with_suffix(vmx_path.suffix + ".bak")
    if not bak.exists():
        bak.write_text(vmx_path.read_text(encoding="utf-8", errors="ignore"), encoding="utf-8")
    vmx_path.write_text(raw, encoding="utf-8")


def read_mode(vmx_path: Path) -> str:
    raw = vmx_path.read_text(encoding="utf-8", errors="ignore")
    m = re.search(r'monitor_control\.restrict_backdoor\s*=\s*"(TRUE|FALSE)"', raw, re.I)
    if not m:
        return "bilinmiyor"
    return "OYUN" if m.group(1).upper() == "TRUE" else "DOSYA"


class App:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("VM Mode Switch")
        self.root.geometry("520x360")
        self.root.configure(bg="#0b1220")
        self.root.resizable(False, False)

        self.vmx = tk.StringVar(value="")
        self.status = tk.StringVar(value="VMX seç → mod değiştir → VM'yi kapat/aç")

        tk.Label(self.root, text="VM Mode Switch", bg="#0b1220", fg="#e8eefc",
                 font=("Segoe UI", 16, "bold")).pack(pady=(16, 4))
        tk.Label(
            self.root,
            text="Native sürükle-bırak için Dosya Modu.\n"
                 "Oyuna girmek için Oyun Modu.\n"
                 "ÖNEMLİ: Değiştirmeden önce sanal KAPALI olsun, sonra aç.",
            bg="#0b1220", fg="#93a4c3", font=("Segoe UI", 9), justify="center",
        ).pack(padx=12)

        row = tk.Frame(self.root, bg="#121a2b")
        row.pack(fill="x", padx=16, pady=14)
        tk.Entry(row, textvariable=self.vmx, bg="#1a2438", fg="#e8eefc",
                 font=("Consolas", 9), relief="flat").pack(
            side="left", fill="x", expand=True, padx=(8, 6), pady=8, ipady=4
        )
        tk.Button(row, text="VMX Seç", command=self.browse, bg="#3b82f6", fg="white",
                  relief="flat", font=("Segoe UI", 9, "bold"), padx=10, pady=4,
                  cursor="hand2").pack(side="right", padx=8)

        btns = tk.Frame(self.root, bg="#0b1220")
        btns.pack(pady=8)
        tk.Button(
            btns, text="📁  DOSYA MODU\n(sürükle-bırak AÇ)",
            command=lambda: self.switch(False),
            bg="#059669", fg="white", font=("Segoe UI", 11, "bold"),
            width=20, height=3, relief="flat", cursor="hand2",
        ).grid(row=0, column=0, padx=8)
        tk.Button(
            btns, text="🎮  OYUN MODU\n(backdoor KAPAT)",
            command=lambda: self.switch(True),
            bg="#dc2626", fg="white", font=("Segoe UI", 11, "bold"),
            width=20, height=3, relief="flat", cursor="hand2",
        ).grid(row=0, column=1, padx=8)

        tk.Label(self.root, textvariable=self.status, bg="#0b1220", fg="#fbbf24",
                 font=("Segoe UI", 10, "bold"), wraplength=480, justify="center").pack(
            pady=16, padx=12
        )

        tk.Label(
            self.root,
            text="İkisi birden olmaz: oyun açık backdoor istemez,\n"
                 "sürükle-bırak ise backdoor ister.",
            bg="#0b1220", fg="#64748b", font=("Segoe UI", 8), justify="center",
        ).pack()

    def browse(self):
        p = filedialog.askopenfilename(
            title="PC-2.vmx seç",
            filetypes=[("VMware VMX", "*.vmx"), ("All", "*.*")],
        )
        if p:
            self.vmx.set(p)
            try:
                mode = read_mode(Path(p))
                self.status.set(f"Seçildi. Şu an mod: {mode}")
            except Exception as e:
                self.status.set(f"Okunamadı: {e}")

    def switch(self, game_mode: bool):
        path = self.vmx.get().strip()
        if not path:
            messagebox.showwarning("VMX", "Önce .vmx dosyasını seç.")
            return
        vmx = Path(path)
        if not vmx.exists():
            messagebox.showerror("VMX", "Dosya yok.")
            return
        if not messagebox.askyesno(
            "Onay",
            ("OYUN MODU" if game_mode else "DOSYA MODU")
            + " uygulanacak.\n\n"
            "Sanal şu an KAPALI mı?\n"
            "(Açıksa önce kapat, sonra bu işlemi yap, sonra tekrar aç.)",
        ):
            return
        try:
            apply_mode(vmx, game_mode=game_mode)
        except Exception as e:
            messagebox.showerror("Hata", str(e))
            return
        if game_mode:
            self.status.set(
                "OYUN MODU yazıldı (backdoor TRUE).\n"
                "Şimdi VM'yi aç → oyuna gir.\n"
                "Sürükle-bırak bu modda ÇALIŞMAZ."
            )
            messagebox.showinfo(
                "Oyun Modu",
                "Hazır.\n1) VM'yi aç\n2) Oyuna gir\n\n"
                "Dosya atacaksan VM'yi kapatıp DOSYA MODU'na geç.",
            )
        else:
            self.status.set(
                "DOSYA MODU yazıldı (backdoor FALSE).\n"
                "Şimdi VM'yi aç → native sürükle-bırak kullan.\n"
                "Oyuna girmeden önce OYUN MODU'na dön."
            )
            messagebox.showinfo(
                "Dosya Modu",
                "Hazır.\n1) VM'yi aç\n2) Ana PC'den sanala sürükle-bırak\n\n"
                "İşin bitince VM'yi kapat → OYUN MODU.",
            )

    def run(self):
        self.root.mainloop()


def main():
    App().run()


if __name__ == "__main__":
    main()
