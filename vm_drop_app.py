"""
VM Drop — tek giriş noktası (EXE için).
Açılışta Ana PC / Sanal PC seçilir.
"""
import tkinter as tk
from tkinter import messagebox


def main():
    root = tk.Tk()
    root.title("VM Drop")
    root.geometry("420x260")
    root.configure(bg="#0b1220")
    root.resizable(False, False)
    try:
        root.tk.call("tk", "scaling", 1.2)
    except Exception:
        pass

    tk.Label(root, text="VM Drop", bg="#0b1220", fg="#e8eefc",
             font=("Segoe UI", 18, "bold")).pack(pady=(28, 6))
    tk.Label(root, text="Bu programı nerede çalıştırıyorsun?",
             bg="#0b1220", fg="#93a4c3", font=("Segoe UI", 10)).pack()

    def start_host():
        root.destroy()
        from host_drop import HostApp
        HostApp().run()

    def start_guest():
        root.destroy()
        from guest_agent import GuestUI
        GuestUI().run()

    fr = tk.Frame(root, bg="#0b1220")
    fr.pack(pady=24)
    tk.Button(fr, text="Ana PC\n(VMware şeridine bırak)",
              command=start_host, bg="#3b82f6", fg="white",
              font=("Segoe UI", 11, "bold"), width=22, height=3,
              relief="flat", cursor="hand2").grid(row=0, column=0, padx=8)
    tk.Button(fr, text="Sanal PC\n(Dosyaları Masaüstüne al)",
              command=start_guest, bg="#059669", fg="white",
              font=("Segoe UI", 11, "bold"), width=22, height=3,
              relief="flat", cursor="hand2").grid(row=0, column=1, padx=8)

    root.mainloop()


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        try:
            messagebox.showerror("VM Drop", str(e))
        except Exception:
            raise
