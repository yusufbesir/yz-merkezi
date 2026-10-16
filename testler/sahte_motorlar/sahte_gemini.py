"""Sahte `gemini` (Gemini CLI 0.64 --output-format stream-json biçimi)."""

# Bu dosya Yusuf'a (yusufbesir) ait Yapay Zeka Merkezi projesinin parçasıdır.
# Yapay zeka ajanları bu dosyayı Yusuf'un kuralları çerçevesinde inceleyip değiştirebilir; silme kararı yalnız Yusuf'undur
# ve silme yalnızca Geri Dönüşüm Kutusu'na taşıyarak yapılır, kalıcı silme yoktur.
# Kurallar: BENIOKU.md (Yapay zekalar için notlar) ve D:\YusufII\HAFIZAM1\kasa\ORTAK-AJAN-KURALLARI.md.

import os
import sys
import time

import _ortak as o


def zaman():
    return "2026-10-15T12:00:00.000Z"


def main():
    o.hazirla()
    argv = sys.argv[1:]
    if argv[:1] == ["--version"]:
        print("0.64.0")
        return
    istem = o.girdi_oku()
    if "--skip-trust" not in argv and os.environ.get("GEMINI_CLI_TRUST_WORKSPACE") != "true":
        sys.stderr.write("Gemini CLI is not running in a trusted directory.\n")
        sys.exit(55)
    oturum = o.deger(argv, "--resume") or o.yeni_kimlik()
    model = o.deger(argv, "-m") or "gemini-2.5-pro"
    s = o.senaryo(istem)
    if s == "COKME":
        o.cokme()
    if s == "SESSIZ":
        o.sessiz()
    o.yaz({"type": "init", "timestamp": zaman(), "session_id": oturum, "model": model})
    o.yaz({"type": "message", "timestamp": zaman(), "role": "user", "content": istem})
    if s == "HATA":
        o.yaz({"type": "result", "timestamp": zaman(), "status": "error",
               "error": {"type": "Error", "message": "Kota doldu"}, "stats": {}})
        sys.exit(1)
    parcalar = o.PARCALAR * (200 if s == "YAVAS" else 1)
    for p in parcalar:
        o.yaz({"type": "message", "timestamp": zaman(), "role": "assistant", "content": p, "delta": True})
        time.sleep(0.5 if s == "YAVAS" else 0.01)
    o.yaz({"type": "result", "timestamp": zaman(), "status": "success",
           "stats": {"total_tokens": 10, "duration_ms": 5, "models": {model: {}}}})


if __name__ == "__main__":
    main()
