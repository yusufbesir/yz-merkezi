"""Gemini CLI motoru: `gemini --output-format stream-json`, başsız (headless) sohbet modu.

Komut (istem standart girdiden; stdin/stdout boru olduğu için CLI başsız çalışır, `-p` gerekmez):
    node <npm>/node_modules/@google/gemini-cli/bundle/gemini.js
         --output-format stream-json --skip-trust --approval-mode default [-m M] [--resume OTURUM]

- `gemini.cmd` (toplu iş dosyası) ÇAĞRILMAZ: kullanıcı metninin cmd.exe'den geçmemesi için doğrudan node + gemini.js.
- `--skip-trust` ve GEMINI_CLI_TRUST_WORKSPACE=true: güvenilmeyen klasörde başsız çalışma reddini (FatalUntrusted
  WorkspaceError) önler. `--approval-mode default`: onay gerektiren araçlar başsız modda çalışmaz (yolo YOK).
- NO_BROWSER=true: giriş yoksa tarayıcı penceresi açılmaz; GEMINI_CLI_NO_RELAUNCH=true: ikinci node süreci açılmaz.
- stream-json olayları: init{session_id, model}, message{role, content, delta}, tool_use, tool_result,
  error{severity, message}, result{status, error?, stats}.
- Oturum: init olayındaki session_id (UUID) → sonraki çağrıda `--resume <uuid>`. Oturumlar proje (çalışma klasörü)
  başına saklanır; devam ettirmek için aynı çalışma klasörü kullanılmalıdır.
- Gemini'nin sistem istemi bayrağı olmadığından talimat istemin başına eklenir.
"""
import json
import os
import shutil
from pathlib import Path

from .taban import Motor

VARSAYILAN_SISTEM = ("Kullanıcıyla sohbet eden bir yardımcısın. Aksi istenmedikçe Türkçe yanıt ver. "
                     "Araç kullanma; yalnızca metinle yanıtla.")
GIRIS_JS = Path("node_modules") / "@google" / "gemini-cli" / "bundle" / "gemini.js"


def gemini_ev():
    return Path(os.environ.get("GEMINI_CLI_HOME") or Path.home()) / ".gemini"


class GeminiMotoru(Motor):
    id = "gemini"
    ad = "Gemini"
    renk = "#4285f4"
    GIRIS_YARDIMI = "Giriş gerekli: terminalde `gemini` çalıştırıp Google hesabınla giriş yap."
    VARSAYILAN_MODELLER = [
        {"id": "gemini-2.5-flash-lite", "ad": "Gemini 2.5 Flash-Lite", "sinif": "hizli"},
        {"id": "gemini-2.5-flash", "ad": "Gemini 2.5 Flash", "sinif": "dengeli"},
        {"id": "gemini-2.5-pro", "ad": "Gemini 2.5 Pro", "sinif": "guclu"},
    ]

    def _exe_bul(self):
        """PATH'teki `gemini(.cmd)` yanındaki npm paketinin gemini.js girişi; yoksa %APPDATA%\\npm."""
        klasorler = []
        bulunan = shutil.which("gemini")
        if bulunan:
            klasorler.append(Path(bulunan).resolve().parent)
        if os.environ.get("APPDATA"):
            klasorler.append(Path(os.environ["APPDATA"]) / "npm")
        for klasor in klasorler:
            for aday in (klasor / GIRIS_JS, klasor / "lib" / GIRIS_JS):
                if aday.is_file():
                    return aday
        return None

    def kurulum_yardimi(self):
        return "Kurmak için: npm install -g @google/gemini-cli"

    def _ortam(self):
        ortam = super()._ortam()
        ortam.update({"GEMINI_CLI_TRUST_WORKSPACE": "true", "NO_BROWSER": "true",
                      "GEMINI_CLI_NO_RELAUNCH": "true", "NO_COLOR": "1"})
        return ortam

    def _giris_denetle(self):
        """Kimlik bilgisi var mı? (Ağa çıkmadan: API anahtarı ortamı ya da ~/.gemini içindeki kimlik dosyası.)"""
        if os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY"):
            return True
        if os.environ.get("GOOGLE_GENAI_USE_VERTEXAI") == "true" or os.environ.get("GOOGLE_GENAI_USE_GCA") == "true":
            return True
        ev = gemini_ev()
        for ad in ("oauth_creds.json", "gemini-credentials.json"):
            yol = ev / ad
            try:
                if yol.is_file() and yol.stat().st_size > 0:
                    return True
            except OSError:
                pass
        return False

    def _komut(self, istem, oturum, model, sistem):
        argumanlar = ["--output-format", "stream-json", "--skip-trust", "--approval-mode", "default"]
        if model:
            argumanlar += ["-m", str(model)]
        if oturum:
            argumanlar += ["--resume", str(oturum)]
        return argumanlar, self._sistemli_istem(istem, sistem or VARSAYILAN_SISTEM)

    def sor(self, istem, **secenekler):
        # Giriş yokken başsız çalıştırmak OAuth akışı başlatır; pencere açmamak için önceden durdurulur.
        if self._giris_denetle() is False:
            yield {"tur": "hata", "mesaj": self.GIRIS_YARDIMI, "giris_gerekli": True}
            return
        yield from super().sor(istem, **secenekler)

    def _satir_isle(self, veri, durum):
        tur = veri.get("type")
        olaylar = []
        if tur == "init":
            if veri.get("session_id"):
                durum["oturum"] = veri["session_id"]
            if veri.get("model"):
                durum["model"] = veri["model"]
            olaylar.append({"tur": "baslangic"})
        elif tur == "message":
            if veri.get("role") == "assistant":
                metin = veri.get("content")
                if isinstance(metin, list):
                    metin = "".join(p.get("text", "") for p in metin if isinstance(p, dict))
                metin = str(metin or "")
                if metin:   # başsız modda yardımcı iletileri hep `delta: true` parçalar olarak gelir
                    durum["parcalar"].append(metin)
                    olaylar.append({"tur": "parca", "metin": metin})
        elif tur in ("tool_use", "tool_result"):
            olaylar.append({"tur": "durum", "metin": "araç kullanıyor…"})
        elif tur == "error":
            if veri.get("severity") == "error" and veri.get("message"):
                durum["hata"] = str(veri["message"])[:300]
            elif veri.get("message"):
                olaylar.append({"tur": "durum", "metin": f"uyarı: {str(veri['message'])[:120]}"})
        elif tur == "result":
            if veri.get("status") == "error":
                hata = veri.get("error") or {}
                mesaj = hata.get("message") if isinstance(hata, dict) else str(hata)
                durum["hata"] = self._hata_metni(mesaj or "bilinmeyen hata")
            else:
                stats = veri.get("stats") or {}
                modeller = stats.get("models") if isinstance(stats, dict) else None
                if not durum.get("model") and isinstance(modeller, dict) and modeller:
                    durum["model"] = next(iter(modeller))
                durum["bitti"] = True
        return olaylar

    def _hata_metni(self, mesaj):
        mesaj = str(mesaj)
        kucuk = mesaj.lower()
        if "auth" in kucuk or "login" in kucuk or "credential" in kucuk:
            return f"{self.GIRIS_YARDIMI} ({mesaj[:200]})"
        return mesaj[:300]

    def _hata_yorumla(self, kod, stderr_ozeti):
        if kod == 41:
            return self.GIRIS_YARDIMI
        if kod == 55 or "trusted directory" in (stderr_ozeti or ""):
            return "Gemini çalışma klasörüne güvenmedi (güvenilir klasör ayarı gerekli)."
        if kod == 42:
            return f"Gemini girdiyi kabul etmedi (çıkış kodu 42). {stderr_ozeti}".strip()
        return super()._hata_yorumla(kod, stderr_ozeti)
