"""Sahte `claude` (Claude Code 2.x stream-json biçimi)."""

# Bu dosya Yusuf'a (yusufbesir) ait Yapay Zeka Merkezi projesinin parçasıdır.
# Yapay zeka ajanları bu dosyayı Yusuf'un kuralları çerçevesinde inceleyip değiştirebilir; silme kararı yalnız Yusuf'undur
# ve silme yalnızca Geri Dönüşüm Kutusu'na taşıyarak yapılır, kalıcı silme yoktur.
# Kurallar: BENIOKU.md (Yapay zekalar için notlar) ve D:\YusufII\HAFIZAM1\kasa\ORTAK-AJAN-KURALLARI.md.

import json
import sys
import time

import _ortak as o


def main():
    o.hazirla()
    argv = sys.argv[1:]
    if argv[:1] == ["--version"]:
        print("2.1.296 (Claude Code)")
        return
    if argv[:2] == ["auth", "status"]:
        print(json.dumps({"loggedIn": o.giris_var(), "authMethod": "claude.ai" if o.giris_var() else "none"}))
        return
    istem = o.girdi_oku()
    oturum = o.deger(argv, "--resume") or o.yeni_kimlik()
    model = o.deger(argv, "--model") or "claude-sahte-1"
    s = o.senaryo(istem)
    if s == "COKME":
        o.cokme()
    if s == "SESSIZ":
        o.sessiz()
    o.yaz({"type": "system", "subtype": "init", "session_id": oturum, "model": model, "tools": []})
    if s == "HATA":
        o.yaz({"type": "result", "subtype": "success", "is_error": True, "session_id": oturum,
               "result": "API Error: aşırı yük"})
        sys.exit(1)
    o.yaz({"type": "stream_event", "session_id": oturum,
           "event": {"type": "message_start", "message": {"model": model}}})
    o.yaz({"type": "stream_event", "session_id": oturum,
           "event": {"type": "content_block_delta", "index": 0, "delta": {"type": "thinking_delta", "thinking": "…"}}})
    parcalar = o.PARCALAR * (200 if s == "YAVAS" else 1)
    for p in parcalar:
        o.yaz({"type": "stream_event", "session_id": oturum,
               "event": {"type": "content_block_delta", "index": 1, "delta": {"type": "text_delta", "text": p}}})
        time.sleep(0.5 if s == "YAVAS" else 0.01)
    tam = "".join(parcalar)
    o.yaz({"type": "assistant", "session_id": oturum,
           "message": {"model": model, "content": [{"type": "text", "text": tam}]}})
    o.yaz({"type": "result", "subtype": "success", "is_error": False, "session_id": oturum, "result": tam,
           "duration_ms": 12})


if __name__ == "__main__":
    main()
