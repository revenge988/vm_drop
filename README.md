# VM Drop

VMware Tools kopyala-yapıştır kapalıyken Ana PC → Sanal PC dosya aktarımı.

## Tek EXE (önerilen)

Release'den `VM_Drop.exe` indir — **Python gerekmez**.

1. Ana PC'de ve her sanalda `VM_Drop.exe` çalıştır
2. Açılışta seç:
   - **Ana PC** → VMware üstündeki mavi şeride dosya bırak
   - **Sanal PC** → adı `PC-1` / `PC-2` yap, dinlemede kalsın
3. Dosya sanalın **Masaüstü**ne iner

Ağ: Bridged veya Host-only. IP gelmezse şeride sağ tık.

Download: [Releases](https://github.com/revenge988/vm_drop/releases)
