"""Codex CLI (codex.exe) motoru: `codex exec --json`, salt okunur kum havuzu, sohbet modu.

Komut (istem standart girdiden, `-`):
    yeni:  codex exec --json --skip-git-repo-check --sandbox read-only [-m M] -
    devam: codex exec resume --json --skip-git-repo-check -c sandbox_mode="read-only" [-m M] THREAD_ID -
           (`exec resume` alt komutunda --sandbox seçeneği yok; aynı ayar -c ile verilir)

JSONL olayları: thread.started{thread_id}, turn.started, item.started/item.updated/item.completed
{item:{id,type,text}}, turn.completed{usage}, turn.failed{error{message}}, error{message}.
Codex'in sistem istemi bayrağı olmadığından talimat istemin başına eklenir.
"""
import json
import os
import re
from pathlib import Path

from .taban import Motor

VARSAYILAN_SISTEM = ("Kullanıcıyla sohbet eden bir yardımcısın. Aksi istenmedikçe Türkçe yanıt ver. "
                     "Komut çalıştırma ve dosya değiştirme; yalnızca metinle yanıtla.")

_HIZLI = ("fast", "affordable", "efficient", "mini")
_GUCLU = ("frontier", "most demanding", "most capable", "max")


def codex_ev():
    return Path(os.environ.get("CODEX_HOME") or (Path.home() / ".codex"))


class CodexMotoru(Motor):
    id = "codex"
    ad = "Codex"
    renk = "#10a37f"
    GIRIS_YARDIMI = "Giriş gerekli: terminalde `codex login` çalıştırıp ChatGPT hesabınla giriş yap."
    # models_cache.json okunamazsa (2026-10 itibarıyla Codex'in listelediği modeller)
    VARSAYILAN_MODELLER = [
        {"id": "gpt-6-luna", "ad": "GPT-6-Luna", "sinif": "hizli"},
        {"id": "gpt-6.1-sol", "ad": "GPT-6.1-Sol", "sinif": "dengeli"},
        {"id": "gpt-6-astra", "ad": "GPT-6-Astra", "sinif": "guclu"},
    ]

    def _exe_bul(self):
        """%LOCALAPPDATA%\\OpenAI\\Codex\\bin\\*\\codex.exe içinde en yeni dosya; yoksa PATH."""
        kok = Path(os.environ.get("LOCALAPPDATA") or Path.home()) / "OpenAI" / "Codex" / "bin"
        adaylar = []
        try:
            adaylar = [p for p in kok.glob("*/codex.exe") if p.is_file()]
        except OSError:
            pass
        if adaylar:
            return max(adaylar, key=lambda p: p.stat().st_mtime)
        bulunan = super()._exe_bul()
        if bulunan and Path(bulunan).suffix.lower() in (".cmd", ".bat"):
            return None
        return bulunan

    def kurulum_yardimi(self):
        return "Codex uygulamasını ya da CLI'yi kur: https://developers.openai.com/codex"

    def _giris_denetle(self):
        kod, cikti, hata = self._yardimci_calistir(["login", "status"])
        if kod is None:
            return None
        metin = (cikti + "\n" + hata).lower()
        if "not logged in" in metin:
            return False
        if kod == 0 and "logged in" in metin:
            return True
        return False if kod != 0 else None

    def varsayilan_model(self):
        """config.toml'daki üst düzey `model = "..."` değeri (yoksa None)."""
        try:
            metin = (codex_ev() / "config.toml").read_text(encoding="utf-8")
        except OSError:
            return None
        for satir in metin.splitlines():
            if satir.strip().startswith("["):
                break
            eslesme = re.match(r'\s*model\s*=\s*"([^"]+)"', satir)
            if eslesme:
                return eslesme.group(1)
        return None

    def modeller(self):
        """Codex'in kendi model önbelleğinden (models_cache.json, visibility=list); okunamazsa sabit liste."""
        try:
            veri = json.loads((codex_ev() / "models_cache.json").read_text(encoding="utf-8"))
            liste = []
            for m in sorted(veri.get("models") or [], key=lambda m: m.get("priority", 99)):
                if m.get("visibility") != "list" or not m.get("slug"):
                    continue
                aciklama = str(m.get("description") or "").lower()
                if any(k in aciklama for k in _HIZLI):
                    sinif = "hizli"
                elif any(k in aciklama for k in _GUCLU):
                    sinif = "guclu"
                else:
                    sinif = "dengeli"
                liste.append({"id": m["slug"], "ad": m.get("display_name") or m["slug"], "sinif": sinif})
            if liste:
                return liste
        except (OSError, ValueError, AttributeError, TypeError):
            pass
        return super().modeller()

    def _komut(self, istem, oturum, model, sistem):
        if oturum:
            argumanlar = ["exec", "resume", "--json", "--skip-git-repo-check", "-c", 'sandbox_mode="read-only"']
        else:
            argumanlar = ["exec", "--json", "--skip-git-repo-check", "--sandbox", "read-only"]
        if model:
            argumanlar += ["-m", str(model)]
        if oturum:
            argumanlar.append(str(oturum))
        argumanlar.append("-")
        return argumanlar, self._sistemli_istem(istem, sistem or VARSAYILAN_SISTEM)

    def sor(self, istem, **secenekler):
        if not secenekler.get("model"):
            # Olaylarda model adı yok; gösterim için yapılandırmadaki varsayılan kullanılır.
            for olay in super().sor(istem, **secenekler):
                if olay.get("tur") == "bitti" and not olay.get("model"):
                    olay["model"] = self.varsayilan_model()
                yield olay
            return
        yield from super().sor(istem, **secenekler)

    def _satir_isle(self, veri, durum):
        tur = veri.get("type")
        olaylar = []
        yazilan = durum.setdefault("_yazilan", {})   # öğe kimliği → gönderilen metin uzunluğu
        if tur == "thread.started":
            if veri.get("thread_id"):
                durum["oturum"] = veri["thread_id"]
            olaylar.append({"tur": "baslangic"})
        elif tur in ("item.started", "item.updated", "item.completed"):
            oge = veri.get("item") or {}
            oge_turu = oge.get("type") or oge.get("item_type")
            if oge_turu in ("agent_message", "assistant_message"):
                kimlik = oge.get("id") or "?"
                metin = str(oge.get("text") or "")
                onceki = yazilan.get(kimlik)
                if onceki is None and metin:
                    if durum["parcalar"]:   # ikinci ve sonraki iletiler arasına boş satır
                        durum["parcalar"].append("\n\n")
                        olaylar.append({"tur": "parca", "metin": "\n\n"})
                    onceki = 0
                if metin and onceki is not None and len(metin) > onceki:
                    ek = metin[onceki:]
                    yazilan[kimlik] = len(metin)
                    durum["parcalar"].append(ek)
                    olaylar.append({"tur": "parca", "metin": ek})
            elif oge_turu == "reasoning":
                olaylar.append({"tur": "durum", "metin": "düşünüyor…"})
            elif oge_turu in ("command_execution", "mcp_tool_call", "web_search", "file_change"):
                olaylar.append({"tur": "durum", "metin": "araç kullanıyor…"})
            elif oge_turu == "error" and oge.get("message"):
                olaylar.append({"tur": "durum", "metin": f"uyarı: {str(oge['message'])[:120]}"})
        elif tur == "turn.completed":
            durum["bitti"] = True
        elif tur == "turn.failed":
            hata = (veri.get("error") or {}).get("message") or "tur başarısız oldu"
            durum["hata"] = self._hata_metni(hata)
        elif tur == "error":
            # Codex geçici akış sorunlarında (yeniden bağlanma) da `error` yayar; tur yine tamamlanabilir.
            mesaj = self._hata_metni(veri.get("message") or "bilinmeyen hata")
            durum["son_hata"] = mesaj
            olaylar.append({"tur": "durum", "metin": f"uyarı: {mesaj[:120]}"})
        return olaylar

    def _hata_metni(self, hata):
        hata = str(hata)
        kucuk = hata.lower()
        if "login" in kucuk or "unauthorized" in kucuk or "401" in kucuk:
            return f"{self.GIRIS_YARDIMI} ({hata[:200]})"
        return hata[:300]
