"""Yapay Zeka Merkezi (masaüstü sürümü).

Bilgisayarda kurulu ChatGPT, Gemini ve Claude programlarını ekranda yan yana dizer;
alttaki tek yazı kutusundan yazılan mesajı işaretli programların hepsine birden gönderir.
API anahtarı gerekmez: programlar kendi hesaplarınla, kendi aboneliklerinle çalışır.
"""
import json
import os
import sys
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, simpledialog, ttk

import pencereler as pc

KOK = Path(__file__).resolve().parent
UYGULAMA_DOSYASI = KOK / "uygulamalar.json"
AYAR_DOSYASI = Path(os.environ.get("YZ_MASAUSTU_AYAR", KOK / "masaustu-ayarlar.json"))
CUBUK_YUKSEKLIGI = 230
VARSAYILAN_KONUM = {"oran_x": 0.5, "alttan": 90}
OGRETME_SURESI = 4


def ayarlari_oku():
    try:
        return json.loads(AYAR_DOSYASI.read_text("utf-8"))
    except (OSError, ValueError):
        return {}


def ayarlari_yaz(ayar):
    gecici = AYAR_DOSYASI.with_suffix(".tmp")
    gecici.write_text(json.dumps(ayar, ensure_ascii=False, indent=2), "utf-8")
    os.replace(gecici, AYAR_DOSYASI)


class Merkez:
    def __init__(self, kok):
        self.kok = kok
        self.ayar = ayarlari_oku()
        self.ayar.setdefault("konumlar", {})
        self.ayar.setdefault("ek_uygulamalar", [])
        self.ayar.setdefault("secili", {})
        self.satirlar = {}  # uygulama id -> {"uyg", "secili", "durum", "pencere"}

        kok.title("Yapay Zeka Merkezi")
        kok.attributes("-topmost", True)
        kok.minsize(640, 200)
        kok.protocol("WM_DELETE_WINDOW", kok.destroy)

        ust = ttk.Frame(kok, padding=(10, 8, 10, 0))
        ust.pack(fill="x")
        ttk.Label(ust, text="◆ Yapay Zeka Merkezi", font=("Segoe UI", 11, "bold")).pack(side="left")
        for metin, komut in [("Program ekle", self.program_ekle), ("Yenile", self.yenile),
                             ("Yan yana diz", self.yan_yana_diz), ("Hepsini aç", self.hepsini_ac)]:
            ttk.Button(ust, text=metin, command=komut).pack(side="right", padx=(6, 0))

        self.liste = ttk.Frame(kok, padding=(10, 6))
        self.liste.pack(fill="x")

        alt = ttk.Frame(kok, padding=(10, 0, 10, 8))
        alt.pack(fill="both", expand=True)
        self.yazi = tk.Text(alt, height=3, wrap="word", font=("Segoe UI", 11), undo=True)
        self.yazi.pack(side="left", fill="both", expand=True)
        self.yazi.bind("<Return>", self._enter)
        sag = ttk.Frame(alt)
        sag.pack(side="right", fill="y", padx=(8, 0))
        ttk.Button(sag, text="Gönder", command=self.gonder).pack(fill="x", ipady=6)
        self.enter_bas = tk.BooleanVar(value=self.ayar.get("enter_bas", True))
        ttk.Checkbutton(sag, text="Enter'a da bas", variable=self.enter_bas,
                        command=self._ayar_kaydet).pack(anchor="w", pady=(6, 0))

        self.durum = ttk.Label(kok, text="", padding=(10, 0, 10, 8), foreground="#555")
        self.durum.pack(fill="x")

        self.yenile()
        self.yazi.focus_set()

    # ------------------------------------------------------------ uygulama listesi

    def uygulamalar(self):
        hazir = json.loads(UYGULAMA_DOSYASI.read_text("utf-8"))
        return hazir + self.ayar["ek_uygulamalar"]

    def yenile(self):
        for cocuk in self.liste.winfo_children():
            cocuk.destroy()
        acik = pc.pencereleri_listele()
        self.satirlar.clear()
        for satir_no, uyg in enumerate(self.uygulamalar()):
            pencere = pc.pencere_bul(uyg, acik)
            secili = tk.BooleanVar(value=self.ayar["secili"].get(uyg["id"], True))
            secili.trace_add("write", lambda *_: self._ayar_kaydet())
            nokta = tk.Label(self.liste, text="●", fg=uyg.get("renk", "#888"))
            nokta.grid(row=satir_no, column=0, padx=(0, 4))
            ttk.Checkbutton(self.liste, text=uyg["ad"], variable=secili, width=16).grid(row=satir_no, column=1, sticky="w")
            ozel_konum = uyg["id"] in self.ayar["konumlar"]
            durum = ("Açık" if pencere else "Kapalı") + (" · yazı kutusu öğretildi" if ozel_konum else "")
            ttk.Label(self.liste, text=durum, width=34, foreground="#1e8e3e" if pencere else "#a33").grid(
                row=satir_no, column=2, sticky="w")
            ttk.Button(self.liste, text="Aç" if not pencere else "Öne getir",
                       command=lambda u=uyg: self.ac_ya_da_getir(u)).grid(row=satir_no, column=3, padx=2)
            ttk.Button(self.liste, text="Yazı kutusunu öğret",
                       command=lambda u=uyg: self.konum_ogret(u)).grid(row=satir_no, column=4, padx=2)
            if uyg in self.ayar["ek_uygulamalar"]:
                ttk.Button(self.liste, text="Kaldır", command=lambda u=uyg: self.program_kaldir(u)).grid(
                    row=satir_no, column=5, padx=2)
            self.satirlar[uyg["id"]] = {"uyg": uyg, "secili": secili, "pencere": pencere}
        acik_sayisi = sum(1 for s in self.satirlar.values() if s["pencere"])
        self.bilgi(f"{acik_sayisi} program açık. Mesajını yaz, Enter ile işaretli programların hepsine gönder.")

    def _ayar_kaydet(self):
        self.ayar["secili"] = {sid: s["secili"].get() for sid, s in self.satirlar.items()}
        self.ayar["enter_bas"] = self.enter_bas.get()
        ayarlari_yaz(self.ayar)

    def bilgi(self, metin, hata=False):
        self.durum.configure(text=metin, foreground="#b3261e" if hata else "#555")

    # ------------------------------------------------------------ düğmeler

    def ac_ya_da_getir(self, uyg):
        pencere = pc.pencere_bul(uyg, pc.pencereleri_listele())
        try:
            if pencere:
                pc.one_getir(pencere.hwnd)
            else:
                pc.uygulamayi_ac(uyg)
                self.bilgi(f"{uyg['ad']} açılıyor…")
                self.kok.after(4000, self.yenile)
        except pc.PencereHatasi as h:
            self.bilgi(str(h), hata=True)

    def hepsini_ac(self):
        acilan = []
        for s in self.satirlar.values():
            if not s["pencere"]:
                try:
                    pc.uygulamayi_ac(s["uyg"])
                    acilan.append(s["uyg"]["ad"])
                except pc.PencereHatasi as h:
                    self.bilgi(str(h), hata=True)
        if acilan:
            self.bilgi(f"Açılıyor: {', '.join(acilan)}. Birkaç saniye sonra yan yana dizilecek.")
            self.kok.after(6000, lambda: (self.yenile(), self.yan_yana_diz()))
        else:
            self.yan_yana_diz()

    def yan_yana_diz(self):
        self.yenile()
        acik = [s for s in self.satirlar.values() if s["pencere"] and s["secili"].get()]
        if not acik:
            return self.bilgi("Dizilecek açık program yok. Önce \"Hepsini aç\" düğmesine basın.", hata=True)
        alan = pc.calisma_alani()
        for s, (x, y, g, y_) in zip(acik, pc.yan_yana_konumlar(alan, len(acik), CUBUK_YUKSEKLIGI)):
            pc.yerlestir(s["pencere"].hwnd, x, y, g, y_)
        sol, _, sag, alt = alan
        self.kok.geometry(f"{sag - sol}x{CUBUK_YUKSEKLIGI - 40}+{sol}+{alt - CUBUK_YUKSEKLIGI + 8}")
        self.kok.lift()
        self.yazi.focus_set()
        self.bilgi(f"{len(acik)} program yan yana dizildi.")

    def konum_ogret(self, uyg):
        pencere = pc.pencere_bul(uyg, pc.pencereleri_listele())
        if not pencere:
            return self.bilgi(f"{uyg['ad']} açık değil. Önce açın.", hata=True)
        pc.one_getir(pencere.hwnd)
        self.kok.lift()

        def say(kalan):
            if kalan:
                self.bilgi(f"Fareyi {uyg['ad']} programının yazı kutusunun üzerine getirin… {kalan}")
                self.kok.after(1000, say, kalan - 1)
                return
            konum = pc.konum_hesapla(pc.dikdortgen(pencere.hwnd), pc.fare_konumu())
            if not (0 <= konum["oran_x"] <= 1 and konum["alttan"] > 0):
                return self.bilgi("Fare programın penceresinin dışındaydı, tekrar deneyin.", hata=True)
            self.ayar["konumlar"][uyg["id"]] = konum
            ayarlari_yaz(self.ayar)
            self.yenile()
            self.bilgi(f"{uyg['ad']} yazı kutusunun yeri kaydedildi.")

        say(OGRETME_SURESI)

    def program_ekle(self):
        acik = [p for p in pc.pencereleri_listele() if p.hwnd != self._kendi_hwnd()]
        if not acik:
            return self.bilgi("Eklenecek açık pencere bulunamadı.", hata=True)
        pencere = tk.Toplevel(self.kok)
        pencere.title("Program ekle")
        pencere.attributes("-topmost", True)
        ttk.Label(pencere, padding=10, wraplength=520, text=(
            "Yeni bir yapay zeka programını (ya da tarayıcıda açık bir sohbet sitesini) açın, "
            "sonra listeden seçip Ekle'ye basın.")).pack(fill="x")
        kutu = tk.Listbox(pencere, width=80, height=14)
        kutu.pack(fill="both", expand=True, padx=10)
        for p in acik:
            kutu.insert("end", f"{p.baslik}  —  {p.exe}")

        def ekle():
            secim = kutu.curselection()
            if not secim:
                return
            p = acik[secim[0]]
            ad = simpledialog.askstring("Program adı", "Bu program hangi adla görünsün?", parent=pencere,
                                        initialvalue=p.baslik[:30])
            if not ad:
                return
            tarayici = p.exe.lower() in {"msedge.exe", "chrome.exe", "firefox.exe", "brave.exe", "opera.exe"}
            yeni = {"id": f"ek-{len(self.ayar['ek_uygulamalar'])}-{p.exe.lower()}", "ad": ad.strip(),
                    "exe": p.exe, "yol": p.yol, "renk": "#9b59b6"}
            if tarayici:
                # Tarayıcıda birçok pencere olabilir; sekme başlığından bir parçayla eşleştir.
                yeni["baslik_icerir"] = simpledialog.askstring(
                    "Başlık parçası", "Bu sitenin pencere başlığında hep geçen kelime (ör. Grok, DeepSeek):",
                    parent=pencere, initialvalue=ad.strip()) or ad.strip()
                yeni.pop("yol")
            self.ayar["ek_uygulamalar"].append(yeni)
            ayarlari_yaz(self.ayar)
            pencere.destroy()
            self.yenile()
            self.bilgi(f"{ad} eklendi. Gerekirse \"Yazı kutusunu öğret\" ile yazı kutusunun yerini gösterin.")

        ttk.Button(pencere, text="Ekle", command=ekle).pack(pady=10)

    def program_kaldir(self, uyg):
        if messagebox.askyesno("Kaldır", f"{uyg['ad']} listeden kaldırılsın mı? (Programın kendisi silinmez.)"):
            self.ayar["ek_uygulamalar"] = [u for u in self.ayar["ek_uygulamalar"] if u["id"] != uyg["id"]]
            self.ayar["konumlar"].pop(uyg["id"], None)
            ayarlari_yaz(self.ayar)
            self.yenile()

    # ------------------------------------------------------------ gönderme

    def _kendi_hwnd(self):
        return int(self.kok.wm_frame(), 16)

    def _enter(self, olay):
        if olay.state & 0x0001:  # Shift+Enter: yeni satır
            return None
        self.gonder()
        return "break"

    def gonder(self):
        metin = self.yazi.get("1.0", "end").strip()
        if not metin:
            return
        self.yenile()
        hedefler = [s for s in self.satirlar.values() if s["secili"].get()]
        if not hedefler:
            return self.bilgi("En az bir programı işaretleyin.", hata=True)
        self.kok.clipboard_clear()
        self.kok.clipboard_append(metin)
        self.kok.update()

        gonderilen, sorunlar = [], []
        for s in hedefler:
            uyg = s["uyg"]
            if not s["pencere"]:
                sorunlar.append(f"{uyg['ad']}: açık değil")
                continue
            konum = self.ayar["konumlar"].get(uyg["id"], VARSAYILAN_KONUM)
            try:
                pc.yaziyi_gonder(s["pencere"].hwnd, konum, enter=self.enter_bas.get())
                gonderilen.append(uyg["ad"])
            except pc.PencereHatasi as h:
                sorunlar.append(f"{uyg['ad']}: {h}")

        pc.one_getir(self._kendi_hwnd())
        self.yazi.focus_set()
        if gonderilen:
            self.yazi.delete("1.0", "end")
        mesaj = f"Gönderildi: {', '.join(gonderilen)}." if gonderilen else "Hiçbir programa gönderilemedi."
        if sorunlar:
            mesaj += "  Sorun: " + "; ".join(sorunlar)
        self.bilgi(mesaj, hata=bool(sorunlar))


def main():
    if sys.platform != "win32":
        print("Bu sürüm yalnızca Windows'ta çalışır.")
        return
    pc.dpi_farkindaligi_ac()
    kok = tk.Tk()
    try:
        ttk.Style().theme_use("vista")
    except tk.TclError:
        pass
    Merkez(kok)
    kok.mainloop()


if __name__ == "__main__":
    main()
