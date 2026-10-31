"""
VM Drop — tek EXE giriş.
1) Dosya/Oyun modu (native sürükle-bırak için VMX)
2) Ana PC ağ şeridi
3) Sanal PC alıcı
"""
import tkinter as tk
from tkinter import messagebox


def main():
    root = tk.Tk()
    root.title("VM Drop")
    root.geometry("520x340")
    root.configure(bg="#0b1220")
    root.resizable(False, False)
    try:
        root.tk.call("tk", "scaling", 1.2)
    except Exception:
        pass

    tk.Label(root, text="VM Drop", bg="#0b1220", fg="#e8eefc",
             font=("Segoe UI", 18, "bold")).pack(pady=(20, 4))
    tk.Label(
        root,
        text="Native sürükle-bırak istiyorsan → Dosya/Oyun Modu\n"
             "(VM kapalıyken değiştir, sonra aç)",
        bg="#0b1220", fg="#93a4c3", font=("Segoe UI", 9), justify="center",
    ).pack()

    def start_switch():
        root.destroy()
        from vm_mode_switch import App
        App().run()

    def start_host():
        root.destroy()
        from host_drop import HostApp
        HostApp().run()

    def start_guest():
        root.destroy()
        from guest_agent import GuestUI
        GuestUI().run()

    fr = tk.Frame(root, bg="#0b1220")
    fr.pack(pady=18)

    tk.Button(
        fr, text="📁 / 🎮  Dosya ↔ Oyun Modu\n(native sürükle-bırak)",
        command=start_switch, bg="#7c3aed", fg="white",
        font=("Segoe UI", 11, "bold"), width=28, height=3,
        relief="flat", cursor="hand2",
    ).grid(row=0, column=0, columnspan=2, padx=8, pady=6)

    tk.Button(
        fr, text="Ana PC\n(ağ ile şeride bırak)",
        command=start_host, bg="#3b82f6", fg="white",
        font=("Segoe UI", 10, "bold"), width=18, height=3,
        relief="flat", cursor="hand2",
    ).grid(row=1, column=0, padx=8, pady=6)

    tk.Button(
        fr, text="Sanal PC\n(ağ ile Masaüstüne al)",
        command=start_guest, bg="#059669", fg="white",
        font=("Segoe UI", 10, "bold"), width=18, height=3,
        relief="flat", cursor="hand2",
    ).grid(row=1, column=1, padx=8, pady=6)

    root.mainloop()


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        try:
            messagebox.showerror("VM Drop", str(e))
        except Exception:
            raise
