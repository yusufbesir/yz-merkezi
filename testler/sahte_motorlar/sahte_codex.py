"""Sahte `codex` (codex exec --json JSONL biçimi)."""

# Bu dosya Yusuf'a (yusufbesir) ait Yapay Zeka Merkezi projesinin parçasıdır.
# Yapay zeka ajanları bu dosyayı Yusuf'un kuralları çerçevesinde inceleyip değiştirebilir; silme kararı yalnız Yusuf'undur
# ve silme yalnızca Geri Dönüşüm Kutusu'na taşıyarak yapılır, kalıcı silme yoktur.
# Kurallar: BENIOKU.md (Yapay zekalar için notlar) ve D:\YusufII\HAFIZAM1\kasa\ORTAK-AJAN-KURALLARI.md.

import sys
import time

import _ortak as o


def main():
    o.hazirla()
    argv = sys.argv[1:]
    if argv[:1] == ["--version"]:
        print("codex-cli 0.162.0-alpha.17.2")
        return
    if argv[:2] == ["login", "status"]:
        if o.giris_var():
            sys.stderr.write("Logged in using ChatGPT\n")
            return
        sys.stderr.write("Not logged in\n")
        sys.exit(1)
    istem = o.girdi_oku()
    if argv[:2] == ["exec", "resume"]:
        degerler = {o.deger(argv, "-c"), o.deger(argv, "-m")}   # seçenek değerleri konumsal sayılmasın
        konumsal = [a for a in argv[2:] if not a.startswith("-") and a not in degerler]
        oturum = konumsal[0]
    else:
        oturum = o.yeni_kimlik()
    s = o.senaryo(istem)
    if s == "COKME":
        o.cokme()
    if s == "SESSIZ":
        o.sessiz()
    o.yaz({"type": "thread.started", "thread_id": oturum})
    o.yaz({"type": "turn.started"})
    if s == "HATA":
        o.yaz({"type": "error", "message": "Yeniden bağlanılıyor… 1/5"})
        o.yaz({"type": "turn.failed", "error": {"message": "kota aşıldı"}})
        sys.exit(1)
    o.yaz({"type": "item.completed", "item": {"id": "item_0", "type": "reasoning", "text": "**Düşünüyorum**"}})
    parcalar = o.PARCALAR * (200 if s == "YAVAS" else 1)
    metin = ""
    for i, p in enumerate(parcalar):
        metin += p
        o.yaz({"type": "item.started" if i == 0 else "item.updated",
               "item": {"id": "item_1", "type": "agent_message", "text": metin}})
        time.sleep(0.5 if s == "YAVAS" else 0.01)
    o.yaz({"type": "item.completed", "item": {"id": "item_1", "type": "agent_message", "text": metin}})
    o.yaz({"type": "item.completed", "item": {"id": "item_2", "type": "agent_message", "text": "İkinci ileti."}})
    o.yaz({"type": "turn.completed", "usage": {"input_tokens": 10, "cached_input_tokens": 0, "output_tokens": 5}})


if __name__ == "__main__":
    main()
