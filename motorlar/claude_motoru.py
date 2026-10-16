"""Claude Code (claude.exe) motoru: `claude -p` + stream-json, araçlar kapalı, sohbet modu.

Komut (istem standart girdiden):
    claude -p --output-format stream-json --verbose --include-partial-messages
           --permission-mode dontAsk --strict-mcp-config --setting-sources project,local
           [--model M] [--resume OTURUM] --append-system-prompt "<sistem>" --tools ""

- `--bare` KULLANILMAZ: abonelik girişini (claude.ai hesabı) okumaz.
- `--tools ""` tüm yerleşik araçları kapatır; `--strict-mcp-config` MCP sunucularını yüklemez;
  `--setting-sources project,local` kullanıcı ayarlarındaki kancaların (hook) sohbet sırasında çalışmasını önler.
- Oturum sürekliliği: `result` olayındaki `session_id` → sonraki çağrıda `--resume`.
"""

# Bu dosya Yusuf'a (yusufbesir) ait Yapay Zeka Merkezi projesinin parçasıdır.
# Yapay zeka ajanları bu dosyayı Yusuf'un kuralları çerçevesinde inceleyip değiştirebilir; silme kararı yalnız Yusuf'undur
# ve silme yalnızca Geri Dönüşüm Kutusu'na taşıyarak yapılır, kalıcı silme yoktur.
# Kurallar: BENIOKU.md (Yapay zekalar için notlar) ve D:\YusufII\HAFIZAM1\kasa\ORTAK-AJAN-KURALLARI.md.

import json
import os
from pathlib import Path

from .taban import Motor

VARSAYILAN_SISTEM = ("Kullanıcıyla sohbet eden bir yardımcısın. Aksi istenmedikçe Türkçe yanıt ver. "
                     "Araç kullanma; yalnızca metinle yanıtla.")


class ClaudeMotoru(Motor):
    id = "claude"
    ad = "Claude"
    renk = "#d97757"
    AYAR_KAYNAKLARI = "project,local"
    GIRIS_YARDIMI = ("Giriş gerekli: terminalde `claude` çalıştırıp /login ile (ya da `claude auth login`) "
                     "Claude hesabınla giriş yap.")
    # `--model` takma adları (Claude Code en güncel sürüme çözer)
    VARSAYILAN_MODELLER = [
        {"id": "haiku", "ad": "Claude Haiku", "sinif": "hizli"},
        {"id": "sonnet", "ad": "Claude Sonnet", "sinif": "dengeli"},
        {"id": "opus", "ad": "Claude Opus", "sinif": "guclu"},
    ]

    def _exe_bul(self):
        aday = Path.home() / ".local" / "bin" / ("claude.exe" if os.name == "nt" else "claude")
        if aday.is_file():
            return aday
        return super()._exe_bul()

    def kurulum_yardimi(self):
        return "Claude Code'u kur: https://claude.com/claude-code"

    def _ortam(self):
        ortam = super()._ortam()
        for ad in ("CLAUDECODE", "CLAUDE_CODE_ENTRYPOINT"):  # iç içe oturum algısını önle
            ortam.pop(ad, None)
        return ortam

    def _giris_denetle(self):
        kod, cikti, _ = self._yardimci_calistir(["auth", "status"])
        if kod is None:
            return None
        try:
            veri = json.loads(cikti)
        except ValueError:
            return None
        if isinstance(veri, dict) and "loggedIn" in veri:
            return bool(veri["loggedIn"])
        return None

    def _komut(self, istem, oturum, model, sistem):
        argumanlar = ["-p", "--output-format", "stream-json", "--verbose", "--include-partial-messages",
                      "--permission-mode", "dontAsk", "--strict-mcp-config",
                      "--setting-sources", self.AYAR_KAYNAKLARI]
        if model:
            argumanlar += ["--model", str(model)]
        if oturum:
            argumanlar += ["--resume", str(oturum)]
        argumanlar += ["--append-system-prompt", sistem or VARSAYILAN_SISTEM]
        argumanlar += ["--tools", ""]   # en sonda: değişken uzunluklu seçenek başka argüman yutmasın
        return argumanlar, istem

    def _satir_isle(self, veri, durum):
        tur = veri.get("type")
        olaylar = []
        if veri.get("session_id"):
            durum["oturum"] = veri["session_id"]
        if tur == "system" and veri.get("subtype") == "init":
            if veri.get("model"):
                durum["model"] = veri["model"]
            olaylar.append({"tur": "baslangic"})
        elif tur == "stream_event":
            olay = veri.get("event") or {}
            if olay.get("type") == "content_block_delta":
                delta = olay.get("delta") or {}
                if delta.get("type") == "text_delta" and delta.get("text"):
                    durum["parcalar"].append(delta["text"])
                    durum["_delta"] = True
                    olaylar.append({"tur": "parca", "metin": delta["text"]})
                elif delta.get("type") == "thinking_delta":
                    olaylar.append({"tur": "durum", "metin": "düşünüyor…"})
            elif olay.get("type") == "message_start":
                model = (olay.get("message") or {}).get("model")
                if model:
                    durum["model"] = model
        elif tur == "assistant":
            ileti = veri.get("message") or {}
            if ileti.get("model"):
                durum["model"] = ileti["model"]
            if not durum.get("_delta"):   # kısmi iletiler gelmediyse tam iletiyi parça say
                metin = "".join(p.get("text", "") for p in ileti.get("content") or []
                                if isinstance(p, dict) and p.get("type") == "text")
                if metin:
                    durum["parcalar"].append(metin)
                    olaylar.append({"tur": "parca", "metin": metin})
        elif tur == "result":
            if veri.get("is_error") or (veri.get("subtype") and veri.get("subtype") != "success"):
                ayrinti = str(veri.get("result") or veri.get("subtype") or "bilinmeyen hata")
                if "login" in ayrinti.lower() or "logged in" in ayrinti.lower():
                    durum["hata"] = self.GIRIS_YARDIMI
                else:
                    durum["hata"] = ayrinti[:300]
            else:
                if isinstance(veri.get("result"), str):
                    durum["tam_metin"] = veri["result"]
                durum["bitti"] = True
        return olaylar
