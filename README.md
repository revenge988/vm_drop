# VM Drop

VMware Tools kopyala-yapıştır / sürükle-bırak kapalıyken Ana PC → Sanal PC dosya aktarımı.

## Sanal PC (bir kez)

1. Bu repoyu ZIP indirip aç
2. `RUN_SANAL_PC.bat` çalıştır
3. Sanal adını VMware sekmesiyle aynı yap (`PC-1`, `PC-2`, …)
4. İsteğe bağlı: `KUR_SANAL_AUTOSTART.bat`

Gereksinim: Python 3 + ağ (Bridged / Host-only)

## Ana PC

1. `RUN_ANA_PC.bat` çalıştır
2. VMware penceresinin üstündeki **mavi şeride** dosya bırak
3. IP gelmezse şeride sağ tık → sanal IP yaz

Dosya sanalın **Masaüstü**ne iner.
