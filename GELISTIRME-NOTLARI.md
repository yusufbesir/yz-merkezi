> Bu dosya Yusuf'a (yusufbesir) ait Yapay Zeka Merkezi projesinin parçasıdır. yazan: [Claude Sonnet 5.5, alt ajan, 2026-10-17]. Yapay zeka ajanları bu dosyayı Yusuf'un kuralları çerçevesinde inceleyip değiştirebilir; silme kararı yalnız Yusuf'undur ve silme yalnızca Geri Dönüşüm Kutusu'na taşıyarak yapılır. Kurallar: BENIOKU.md ve D:\YusufII\HAFIZAM1\kasa\ORTAK-AJAN-KURALLARI.md.

# Geliştirme notları

Fikir ve yapılacaklar listesi. Ayrıntılar `arastirma/` altındaki araştırma dosyalarındadır.

## OpenCode'dan alınacak fikirler (2026-10-17)

Ayrıntı: `arastirma/opencode-arastirmasi.md`. Önerilen yol: önce (a) fikirleri kendi koduna taşı, sonra isteğe bağlı (b) `opencode run` ile dördüncü motor; (c) OpenCode sunucusunu arka uç yapmak önerilmez.

1. Goal döngüsü: hedef + her tur sonrası değerlendirme + en çok N otomatik tur (M).
2. Kullanım/maliyet takibi: jeton, önbellek, tahmini maliyet, `bitti` olayına (S).
3. Önbellek farkındalıklı yönlendirme; keep-alive yalnız isteğe bağlı, varsayılan kapalı (S-M).
4. Proje notları / To-Do / planlar paneli, hassas taramadan geçen yerel dosya (M).
5. OpenCode'u dördüncü motor yapma (`opencode run --format json`, tüm araçlar deny, `--auto` yok); Yusuf'un kurulum onayı gerekir (M-L).
6. İzin modeli: bir kez / oturum / reddet + desen eşlemeli kural dili, varsayılan ask/deny (M).
7. Zamanlanmış görevler: yalnız sohbet kipi, uygulama açıkken (M).
8. İş bitti / onay bekliyor masaüstü bildirimi, onayda ham komut (S).
9. Mini Sohbet penceresi (üstte sabit ikinci Edge --app penceresi) (S-M).
10. Çoklu çalıştırma (en çok 3 motor) ve kullanıcı seçimi (M).
11. `SKILL.md` biçimini salt metin istem şablonu olarak içe alma (M).
12. Uzak erişim (tünel/Android): ertelendi, önce güvenlik tasarımı (L).
