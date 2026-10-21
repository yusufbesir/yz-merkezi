> Bu dosya Yusuf'a (yusufbesir) ait Yapay Zeka Merkezi projesinin parçasıdır.
> Yapay zeka ajanları bu dosyayı Yusuf'un kuralları çerçevesinde inceleyip değiştirebilir; silme kararı yalnız Yusuf'undur
> ve silme yalnızca Geri Dönüşüm Kutusu'na taşıyarak yapılır, kalıcı silme yoktur.
> Kurallar: BENIOKU.md (Yapay zekalar için notlar) ve D:\YusufII\HAFIZAM1\kasa\ORTAK-AJAN-KURALLARI.md.

# Yapay Zeka Merkezi

Tek bir yapay zeka gibi çalışan Türkçe masaüstü uygulaması. Bir mesaj yazarsın; uygulama her mesaj için en uygun motoru (Claude, Codex/ChatGPT ya da Gemini) kendisi seçer ve yanıtı tek bir akışta gösterir. Hiçbir başka uygulamaya ya da pencereye mesaj göndermez.

İki sürümü var:

1. **Masaüstü sürümü (`baslat.bat`)**: varsayılan kip **Tek Asistan**'dır (aşağıda). Eski çoklu pencere yöntemi (ChatGPT, Gemini ve Claude web siteleri ve masaüstü programları) **Ayarlar → Gelişmiş** altına taşındı; kod silinmedi.
2. **API sürümü (`baslat-api.bat`)**: tarayıcıda çalışır, API anahtarlarıyla bağlanır.

## Tek Asistan (varsayılan kip)

`baslat.bat` ile açılan pencerede tek bir sohbet vardır:

- **Motorlar**: bu bilgisayarda kurulu üç komut satırı aracı (Claude, Codex, Gemini) arka planda `motorlar/` paketi üzerinden çalıştırılır. Her biri kendi hesabınla bir kez giriş yapılarak kullanılır; bu uygulamaya parola ya da API anahtarı yazılmaz. Kenar çubuğunun altındaki **Motorlar** bölümünde her motor için durum noktası görünür: **Hazır** (yeşil), **Giriş gerekli** (turuncu), **Kurulu değil** (gri). Birine tıklayınca ne yapman gerektiğini anlatan not açılır (kurulum ve giriş komutları, Kopyala düğmeli, ve "Yeniden denetle").
- **Sohbet**: senin mesajların sağda, asistan yanıtı solda. Yanıtın üstünde küçük bir rozet hangi motorun ve modelin yanıtladığını gösterir ("Claude · Sonnet 5.5"; rozetin üstüne gelince seçim sebebi). Yanıt parça parça akar, "durum" mesajları rozetin altında solgun tek satır olarak görünür ("Gemini hazır değil, Claude ile devam ediyorum"). Markdown (başlık, kalın/italik, liste, tablo, alıntı, kod bloğu + Kopyala) güvenli DOM ile çizilir. Oto-kaydırma yalnızca en alttayken olur; yukarıdaysan "↓" düğmesi çıkar. `prefers-reduced-motion` tercihi saygı görür.
- **Yazı kutusu**: soldaki **Otomatik ▾** seçici (Otomatik / Claude / Codex / Gemini; seçim ayarlara kaydedilir), sağda gönder oku; yanıt sürerken **Durdur** (kare) düğmesi ya da `Esc`. Yanıtın altında **Yeniden sor ▾**: aynı soruyu başka motora sorar (son soru-yanıt çiftinin yerine geçer).
- **Hassas bilgi uyarısı**, **Hafıza OS bağlamı** ve **Jev** aynen çalışır (aşağıdaki bölümlere bak); hassas bilgi bulunursa gönderilmeden önce şerit çıkar ("Yine de gönder / Vazgeç").
- **Süreklilik**: aynı motorla devam edince motorun kendi oturumu kullanılır. Motor değişirse (ya da motorun oturumu yoksa) son 6 mesajın kısa transkripti istemin başına "Önceki konuşma özeti" olarak eklenir.
- **Yedek motor**: seçilen/önerilen motor hazır değilse sıradaki uygun motora geçilir.

### Motor seçimi (yönlendirici)

`POST /api/sor` her mesajı sınıflandırır (tür: kod, çeviri, özet, araştırma, yazı, matematik, sohbet; zorluk: basit, orta, zor; Jev açık ve hazırsa Jev ile, değilse kurallarla; hassas metin Jev'e gitmez) ve `yonlendirme.json` tercih sırasındaki **ilk hazır motoru** seçer. Başlangıç değerleri: basit → hızlı sınıf (Gemini › Codex › Claude); orta → dengeli (Claude › Codex › Gemini); zor → güçlü (Claude › Codex › Gemini); kod her zorlukta önce Claude; çeviri ve özet önce Gemini hızlı; zor araştırma önce Gemini güçlü. Model adı `motorlar` paketinin `modeller()` listesinden sınıfa göre seçilir; **Ayarlar → Motorlar**'da sınıf başına tercih edilen model seçilebilir (`motor_modelleri` ayarı).

`yonlendirme.json` biçimi (eski `site`/`model_icerir` biçimi geçersiz sayılır, yerleşik varsayılana düşülür ve Ayarlar → Yönlendirme'de uyarı çıkar):

```
{
  "varsayilan": {"basit": [TERCIH, ...], "orta": [...], "zor": [...]},
  "turler": {"kod": {"basit": [...], "orta": [...], "zor": [...]}, "ceviri": {"hepsi": [...]}}
}
TERCIH = {"motor": "claude" | "codex" | "gemini", "sinif": "hizli" | "dengeli" | "guclu"}
```
Aranış: `turler[tür][zorluk]` → `turler[tür]["hepsi"]` → `varsayilan[zorluk]`. `_` ile başlayan anahtarlar yok sayılır; geçersiz bölümler yerleşik varsayılana düşer. `YZ_YONLENDIRME` ortam değişkeni dosya yolunu değiştirir.

### Sunucu uçları (Tek Asistan)

- `POST /api/sor` `{metin, sohbet?, motor?: "otomatik"|"claude"|"codex"|"gemini", model?, onayli?, yeniden?}` → NDJSON akışı (satır başına bir JSON). Sıra: hassas bilgi varsa **tek** `{"tur":"onay_gerekli",...}` olayı ve biter; yoksa `{"tur":"secim","sohbet","motor","motor_ad","renk","model","model_ad","sinif","sebep","kaynak": "jev"|"kural"|"kullanici","yedek"}`, (yedek motor için) `{"tur":"durum","metin"}`, motorun olayları aynen (`baslangic`, `parca`, `durum`, `bitti`, `hata`), sonda `{"tur":"kayit","sohbet","mesaj_sira"}`. Doğrulama hataları akış başlamadan HTTP 400 olur. Kullanıcı mesajı akış başlamadan, asistan mesajı (hata ve durdurulmuş yanıt dahil) akış sonunda `{"rol":"asistan","metin","motor","model","sure"}` olarak yerel geçmişe yazılır; bağlantı kopsa da kısmi yanıt saklanır. Sohbet kaydında `motor_oturumlari: {motor: oturum}` tutulur.
- `POST /api/durdur` `{sohbet}` → süren yanıtı iptal eder (iptal olayı motora geçer).
- `GET /api/durum` → `motorlar: [{id, ad, renk, hazir, sebep, giris, surum}]` (60 sn önbellek; `?motor_yenile=1` önbelleği atlar). Hazır değilse `sebep` giriş talimatını içerir. `motorlar` paketi yüklenemezse üç motor "Motorlar hazır değil" sebebiyle hazır değil görünür; uygulama kırılmaz.
- `GET /api/motor-modelleri` → `{motor: [{id, ad, sinif}]}`; `POST /api/oneri` `{metin}` → tür, zorluk, kaynak ve her öneride motor, sınıf, `hazir`, `model`/`model_ad`; `GET /api/yonlendirme` → kural tablosu, dosya yolu, son sınıflandırma.
- Ayarlar: `varsayilan_motor` ("otomatik" ya da motor kimliği), `motor_modelleri` (`{motor: {sinif: model kimliği}}`).

### Ayarlar sekmeleri

Genel, Görünüm, **Motorlar** (durum, giriş talimatları, tercih edilen modeller), **Yönlendirme** (tablo, yeni biçim), Hafıza, Jev, **Gelişmiş** (eski Hesaplar (web) / Programlar / Hepsini aç / Yan yana diz, "Enter'a da bas", yerleşim, "Yanıtları Jev ile puanla" ve çoklu pencereye gönder), Kısayollar, Hakkında. Kısayollar: Enter gönder, Shift+Enter yeni satır, Ctrl+Shift+O yeni sohbet, Ctrl+B kenar çubuğu, Ctrl+K sohbet ara, Ctrl+, ayarlar, Esc yanıtı durdur.

Yanıt puanlama (Jev ile en iyi yanıtı seçme) tek motorda anlamsız olduğundan yalnızca Gelişmiş'teki çoklu pencere gönderiminde kullanılır.

## Gelişmiş: çoklu pencere yöntemi (eski)

Aşağıdaki anlatım Ayarlar → Gelişmiş altındaki eski yöntemi ve sunucu uçlarını (`/api/gonder`, `/api/yanit`, `/api/site-ac`, ...) anlatır; Tek Asistan bunları kullanmaz.

## Masaüstü sürümü

`baslat.bat` dosyasına çift tıkla; Claude masaüstü uygulamasıyla aynı düzende bir "Yapay Zeka Merkezi" penceresi açılır (Edge'in uygulama penceresinde çalışır, adres çubuğu yoktur). Uygulama zaten çalışıyorsa `baslat.bat` yeni bir kopya başlatmaz, çalışan uygulamaya pencereyi yeniden açtırır. Uygulama (arka uç) kapanınca onun açtığı Edge pencereleri de kapanır.

**Önce web hesapları, masaüstü programları yedek.** ChatGPT, Gemini ve Claude web siteleri bu uygulamanın kendi Edge profilinde (`%LOCALAPPDATA%\YZMerkezi\tarayici-profili`) açılır ve arka planda denetlenir; fare ve klavye taklidi gerekmez. API anahtarı yoktur, kendi hesapların ve aboneliklerin kullanılır.

İlk kullanım:
1. Sol kenar çubuğunda "Hesaplar ve programlar" altındaki **ChatGPT**, **Gemini** ve **Claude**'a tıkla; her biri kendi penceresinde açılır.
2. Açılan pencerede bir kez giriş yap. Oturum o profilde kalır; kullandığın normal Edge profiline dokunulmaz. Durum "Giriş yapıldı" (yeşil), "Giriş gerekli" (turuncu) ya da "Kapalı" olarak görünür; giriş gerekiyorsa yazı kutusunun üstünde bir uyarı şeridi çıkar.
3. Mesajı yaz; işaretli hesapların hepsine aynı anda gider, yanıtlar mesajın altında canlı akar (yazıyor… imleciyle) ve yerel geçmişe kaydedilir.

Düzen:
- **Sol kenar çubuğu**: Yeni sohbet, sohbet arama (hem yerel hem site sohbetlerinde), hesap ve program listesi, **Son sohbetler** (önce "Yapay Zeka Merkezi" ortak sohbetleri, sonra her sitenin kendi sohbetleri; ↻ Yenile düğmesi), en altta adın ve Ayarlar.
- **Orta alan**: karşılama (günün saatine göre), gönderdiğin mesajlar ve her mesajın altında site başına yanıt bloğu. Bir site sohbetine tıklarsan sohbet o sitenin penceresinden okunur: senin mesajların sağda, asistanın yanıtları solda (site rengi ve adıyla). Bu sohbetteyken mesaj yalnızca o siteye, o sohbete gider (istersen başka hedef de işaretleyebilirsin).
- **Yazı kutusu**: altta yuvarlak kutu. Sağdaki seçiciden mesajın gideceği hesapları ve (yedek olarak) masaüstü programlarını işaretlersin; turuncu ok ya da Enter ile gönderirsin, Shift+Enter yeni satır. Yeni sohbette site pencereleri de yeni sohbet sayfasına gider.
- **Mesaj hangi sohbete gider?** Her gönderimde hedef sayfa açıkça seçilir ve site penceresi o sırada hangi sohbeti gösteriyorsa ona yazılmaz:
  - Ortak (Yapay Zeka Merkezi) sohbetinin ilk mesajı her sitede yeni bir sohbet açar. Yanıt gelince sitenin o sohbete ait adresi (ChatGPT `/c/…`, Claude `/chat/…`, Gemini `/app/…`) kaydedilir; sonraki mesajlar her sitede o adrese gider.
  - Bir site sohbetindeyken mesaj o sohbete gider; ayrıca işaretlediğin diğer siteler yeni sohbette yazar. Adres hiçbir siteye ait değilse hiçbir şey gönderilmez.
  - Sayfaya gidildikten sonra adres yeniden okunur; site başka bir sayfaya yönlendirdiyse (ör. sohbet silinmiş) o siteye gönderilmez ve sebebi Türkçe gösterilir.
- **Üst çubuk**: Hepsini aç, Yan yana diz (açık site pencereleri ve masaüstü programları), sohbeti yeniden adlandırma.

Ayarlar (sol alttaki adına tıkla ya da Ctrl+,):
- **Genel**: adın, Enter'a da bas, gönderince kutuyu temizle, çoklu hedefte onay, göndermeden önce hassas bilgi uyarısı, otomatik yönlendirme, yerleşim (bu pencere solda sütun mu altta çubuk mu).
- **Görünüm**: tema (Açık / Koyu / Sistem), yazı boyutu.
- **Programlar**: üstte "Hesaplar (web)" (durum ve "Pencereyi aç / Öne getir"), altta yedek masaüstü programları (Aç, Yazı kutusunu öğret, Kaldır; yeni program ekleme).
- **Yönlendirme**: tür/zorluk tercih tablosunun salt okunur görünümü, `yonlendirme.json` yolu ve düğmesi, son sınıflandırma.
- **Jev**: Jev açık/kapalı, yanıtları Jev ile puanla, uzak sunucu uyarısı ve durum (bkz. "Jev" bölümü).
- **Kısayollar**: Enter gönder, Shift+Enter yeni satır, Ctrl+Shift+O yeni sohbet, Ctrl+B kenar çubuğu, Ctrl+, ayarlar, Ctrl+Shift+D yan yana diz.

Yedek yol (masaüstü programları): bilgisayarında kurulu ChatGPT, Gemini ve Claude programlarına pano ve tuş taklidiyle yazar. İlk açılışta seçili değildir; mesaj kutusundaki seçiciden işaretlersin.
- **Yazı kutusunu öğret**: bir programda mesaj yanlış yere gidiyorsa bu düğmeye bas, 4 saniye içinde fareyi o programın yazı kutusunun üstüne getir. Yer kaydedilir, pencere boyutu değişse de doğru çalışır.
- **Program ekle** (yazı kutusundaki + düğmesi): yeni bir yapay zeka programı kurduğunda ya da tarayıcıda bir sohbet sitesi açtığında onu aç, listeden seç.
- Gönderme sırasında fare ve klavye bir iki saniye programlar arasında gezer; o sırada fareye dokunma. Bir program öne getirilemezse ona hiçbir şey yazılmaz.
- Claude masaüstü uygulamasında hangi sohbet açıksa mesaj oraya gider.

Notlar:
- Site seçicileri (düğmeler, yazı kutusu, sohbet listesi) siteler güncellendikçe bozulabilir; hepsi `siteler.py` içinde tek yerdedir. Bir site yanıt vermezse sebep yazı kutusunun altındaki satırda görünür.
- Site pencerelerini kapatmak oturumu silmez; çerezler `%LOCALAPPDATA%\YZMerkezi\tarayici-profili` klasöründe kalır (proje klasöründe değil, GitHub'a gitmez). Uygulama çerezleri, belirteçleri ya da parolaları okumaz.
- **Masaüstü kısayolu ve simge**: `kisayol-olustur.ps1` dosyasını PowerShell ile çalıştırırsan Masaüstünde simgeli bir "Yapay Zeka Merkezi" kısayolu oluşur (`powershell -ExecutionPolicy Bypass -File kisayol-olustur.ps1`). Simge özgündür (`arayuz-masaustu/simge.svg`); PNG ve ICO dosyaları `python araclar/simge_uret.py` ile yeniden üretilir (Edge gerekir, ek paket yok).
- Ayarlar ve yerel sohbet geçmişi `%LOCALAPPDATA%\YZMerkezi\masaustu-ayarlar.json` dosyasında durur. Arka uç `http://127.0.0.1:8766` adresinde yalnızca bu bilgisayardan erişilebilir.
- Veri konumu: varsayılan klasör `%LOCALAPPDATA%\YZMerkezi` (`YZ_VERI_KLASORU` ile değiştirilebilir); tek tek `YZ_MASAUSTU_AYAR`, `YZ_AYAR_DOSYASI`, `YZ_TARAYICI_PROFILI` ortam değişkenleri önceliklidir. Eski sürümlerden proje klasöründe kalan `masaustu-ayarlar.json`, `ayarlar.json` ve `.tarayici-profili` ilk açılışta bir kez bu klasöre taşınır (profil açık bir Edge tarafından kullanılıyorsa taşınmaz; Edge'i kapatıp yeniden aç).

## Yönlendirme ve hassas bilgi uyarısı

İkisinin de temeli kural tabanlıdır (`hassas.py` ve `yonlendirici.py`, bu bilgisayarda çalışır, mesaj metnini kaydetmez). **Jev açıksa** (Ayarlar → Jev, varsayılan açık) ikisi de ayrıca TypeSafe'in Jev karar modeline danışır ve mesaj metni Jev'in uzak sunucusuna gider; ayrıntılar ve yedek davranış aşağıdaki "Jev" bölümünde. Jev kapalıysa, hazır değilse ya da hata verirse yalnızca kurallar kullanılır.

### Hassas bilgi uyarısı

Gönder'e basınca (Enter ya da ok) mesaj, siteye/motora gitmeden önce taranır. Şu kalıplar aranır:
- **API anahtarı / erişim belirteci** (yüksek önem): `sk-…` (16+ karakter), `sk-ant-…`, `sk-proj-…`, `AIza…` (30+), AWS `AKIA…`/`ASIA…` (ve `aws … secret = <40 karakter>`), Google OAuth `ya29.…`, GitHub `ghp_/gho_/ghu_/ghs_/ghr_…` ve `github_pat_…`, Slack `xoxa-/xoxb-/xoxp-/xoxr-/xoxs-…`, Stripe `sk_live_…`/`rk_live_…`, SendGrid `SG.….…`, Twilio `SK` + 32 onaltılık, JWT (`eyJ….….…`), `Bearer <belirteç>` ve `-----BEGIN … PRIVATE KEY-----` blokları (END satırına kadar).
- **Parola** (yüksek önem): `parola`, `şifre`, `password`, `pin` + `:` ya da `=` + değer (aynı satırda), `eposta:parola` çifti ve parolalı bağlantı dizeleri (`postgres://kullanici:parola@…`, `mysql://`, `mongodb(+srv)://`, `redis://`, `amqp://` …, `Server=…;Password=…`).
- **Kimlik** (yüksek önem): 11 haneli T.C. kimlik kalıbı; rastgele 11 haneli sayılar uyarı çıkarmasın diye algoritma denetimlidir (ilk hane 0 olamaz, 10. ve 11. hane kuralı).
- **Finansal** (yüksek önem): `TR` IBAN kalıbı ve 16 haneli kart numarası (boşluklu ya da tireli; Luhn sağlaması geçmeyen diziler kart sayılmaz).
- **Kişisel** (düşük önem): Türk cep telefonu (`05xx …`, `+90 5xx …`) ve e-posta adresi.
- **Olası anahtar** (düşük önem): 32+ karakterlik, harf ve rakam karışık, yüksek entropili (base64 benzeri için > 4,5 bit/karakter; onaltılık için > 3,5) dizeler. URL'nin şema/ana makine/yol kısmı bu denetimin dışındadır; sorgu ve parça değerleri (`?token=…`, `&key=…`) taranır. Tarama doğrusal sürelidir (kalıplarda sınırlı niceleyiciler) ve en çok 100.000 karakteri tarar (`kirpildi` alanı); `maskele` uzun metni 100.000 karakterlik parçalarla işler.

Düşük önemli bulgular gönderimi durdurmaz, yalnızca uyarı (`hassas_uyari` olayı / alanı) çıkar; ama bu mesajlar Jev'e hiç gönderilmez (bkz. "Güvenlik"). Sıradan Türkçe cümleler, URL'ler ve tarihler bulgu sayılmaz (`testler/test_hassas.py` pozitif ve negatif örnekleri).

Bir şey bulunursa mesaj **gönderilmez** ve yazı kutusunun üstünde bir şerit çıkar: "Bu mesaj <bir API anahtarı / bir parola / bir T.C. kimlik numarası / bir IBAN ya da kart numarası> içeriyor olabilir. **Yine de gönder** / **Vazgeç**". "Yine de gönder" aynı mesajı `onayli: true` ile yeniden yollar; şerit görünürken metni değiştirirsen şerit kapanır ve yeni metin yeniden denetlenir. Birden çok kategori varsa şu öncelik kullanılır: API anahtarı, parola, kimlik, finansal, olası anahtar, kişisel. Sunucu (`POST /api/gonder`) uyarı gerekiyorsa hiçbir yere yazmadan `{"onay_gerekli": true, "kategori", "aciklama"}` döndürür (HTTP 200). Anahtar: **Ayarlar → Genel → "Göndermeden önce hassas bilgi uyarısı"** (varsayılan açık). Tarama bir güvenlik ağıdır, kusursuz değildir: kalıba uymayan bir sırrı (örneğin kelimelerle yazılmış bir parolayı) yakalayamaz.

### Ajan seçimi (yönlendirici, eski site kipi)

> Not: bu bölüm ve "Kuralları düzenleme" eski `site`/`model_icerir` biçimini anlatır. Güncel biçim ve Tek Asistan davranışı yukarıdaki "Motor seçimi" bölümündedir.

Yazarken (600 ms duraklayınca) mesaj kurallarla sınıflandırılır ve yazı kutusunun üstünde bir öneri şeridi çıkar: "Önerilen: Gemini · <model> (basit · araştırma) — **Uygula** / **Değiştir**".
- **Tür**: `kod` (kod bloğu ya da fonksiyon/hata/python/javascript/sql), `ceviri` (çevir/translate/ingilizce/türkçeye), `ozet` (özetle/kısaca), `arastirma` (araştır/karşılaştır/kaynak/neden), `yazi` (yaz/taslak/mail/makale), `matematik` (sayısal ifade ya da denklem), değilse `sohbet`. Birden çok kural uyarsa bu sıradaki ilki kazanır.
- **Zorluk**: uzunluk (200 karakterden kısa `basit`, 1200'den kısa `orta`, üstü `zor`); "ayrıntılı, kapsamlı, analiz, mimari, strateji, plan" geçerse +1 kademe, çok adımlı istek ("önce … sonra" ya da 3+ madde) +1 kademe (en çok `zor`).
- **Uygula**: yalnızca önerilen siteyi hedef yapar ve gönderim isteğine `model_sec: {"site", "model"}` ekler; sunucu mesajı yazmadan önce sitenin model menüsünden o modeli seçer. Seçilemezse (menü değişmiş, model yok, desteği henüz yok) mesaj **mevcut modelle yine gider** ve sorunlara "model seçilemedi: <sebep>" eklenir. Gönderince hedef seçimin eski haline döner. **Değiştir**: sıradaki öneriye geçer. Bir site sohbeti açıkken şerit çıkmaz.
- **Otomatik yönlendirme** (Ayarlar → Genel, varsayılan **kapalı**): açıkken öneri kendiliğinden uygulanır; şerit yine görünür ("Otomatik seçildi: …") ve Değiştir ile başka öneriye geçebilirsin.
- **Model adı**: kurallarda tam model kimliği yazılmaz, yalnızca ad parçası yazılır (ör. `flash`, `sonnet`, `gpt`). Gerçek model, ilgili sitenin canlı model menüsünden (`GET /api/modeller?site=`, 60 sn önbellekli; site açık ve giriş yapılmışsa) büyük/küçük harf duyarsız "içerir" eşleşmesiyle bulunur; ilk eşleşen alınır. Menü okunamazsa ya da eşleşme yoksa yalnızca site önerilir ve sebebi şeritte yazar. Yeni bir sürümü hedeflemek için parçayı uzat (ör. `sonnet 5.5`).
- Sunucu uçları: `POST /api/oneri` `{metin}` → `{tur, zorluk, oneriler: [{site, model_icerir, model, sebep}], kaynak: "kural" | "jev"}`; `GET /api/yonlendirme` (kural tablosu, dosya yolu, son sınıflandırma; mesaj metni içermez); `POST /api/yonlendirme-ac` (kural dosyasını varsayılan düzenleyicide açar).

### Kuralları düzenleme: `yonlendirme.json`

Tercih sırası **kullanıcı veri klasöründeki** `%LOCALAPPDATA%\YZMerkezi\yonlendirme.json` dosyasındadır (`YZ_YONLENDIRME` ile değişir). Bu kopya yoksa ilk okumada paketteki `yonlendirme.json` (şablon) oraya kopyalanır; var olan kopyaya hiç dokunulmaz, yani sürüm güncellenip eski sürüm klasörü temizlense de düzenlemelerin kalır. Ayarlar → Yönlendirme sekmesinde yolu, salt okunur tablosu, son sınıflandırma sonucu ve "yonlendirme.json dosyasını aç" düğmesi (veri klasöründeki kopyayı açar) vardır. JSON'da yorum satırı olmadığı için açıklama burada:

```
{
  "varsayilan": {"basit": [TERCIH, ...], "orta": [...], "zor": [...]},   // her tür için geçerli genel sıra
  "turler": {
    "kod":    {"basit": [...], "orta": [...], "zor": [...]},             // türe özel, zorluğa göre
    "ceviri": {"hepsi": [...]}                                           // "hepsi": her zorluk için
  }
}
TERCIH = {"site": "gemini" | "chatgpt" | "claude", "model_icerir": "flash"}
```
- Bir (tür, zorluk) için aranış: `turler[tür][zorluk]`, yoksa `turler[tür]["hepsi"]`, yoksa `varsayilan[zorluk]`. Listedeki sıra tercih sırasıdır; ilk tercih en uygun olandır. Başlangıç değerleri: basit → Gemini `flash`, ChatGPT `mini`, Claude `haiku`; orta → Claude `sonnet`, ChatGPT `gpt`, Gemini `pro`; zor → Claude `opus`, ChatGPT `pro`, Gemini `pro`; kod her zorlukta önce Claude; çeviri ve özet önce Gemini `flash`; zor araştırma önce Gemini `pro`.
- `_aciklama` gibi `_` ile başlayan ya da tanınmayan anahtarlar yok sayılır. Geçersiz bir bölüm (bilinmeyen site, boş ad, bozuk liste) o bölüm için yerleşik varsayılana düşer; dosya yoksa ya da JSON bozuksa tamamı yerleşik varsayılana düşer ve Ayarlar → Yönlendirme'de uyarı görünür. Uygulama açılışta kırılmaz. Değişiklik bir sonraki öneride geçerlidir (yeniden başlatma gerekmez).
- Testlerde başka bir dosya kullanmak için `YZ_YONLENDIRME` ortam değişkeni yolu değiştirir (testler gerçek veri klasörüne yazmaz).

## Jev

Jev, TypeSafe AI'ın karar (sınıflandırma) modelidir. Uygulama onu üç yerde kullanır; her yerde kural tabanlı yol **yedek** olarak kalır. **Mesajların ve seçtiğin durumlarda yanıtların TypeSafe'in uzak Jev sunucusuna gider (kullanıcı onayı 2026-10-11, proje sohbeti). Yeni bir Jev sürümü ya da yerel seçenek çıkınca yeniden değerlendirilecek.** Jev dışında hiçbir uzak servise veri gönderilmez.

1. **Hassas bilgi uyarısı**: önce yerel tarama (`hassas.tara`). Yerel tarama bir şey bulamazsa ve Jev açıksa metin Jev'e "parola / api_anahtari / kimlik_bilgisi / finansal / yok" seçenekleriyle sorulur. Jev "yok" dışında bir şey seçer ve o seçeneğin olasılığı **≥ 0,6** ise aynı onay şeridi çıkar (`onay_gerekli`, `kaynak: "jev"`, açıklamada "Jev'in değerlendirmesine göre"). Yerel tarama bir şey bulduysa, kullanıcı "Yine de gönder" dediyse ya da uyarı kapalıysa Jev'e sorulmaz. Jev hata verirse sessizce yerel sonuç geçerlidir. Jev sorusu ayar kilidi dışında yapılır (en çok 8 sn).
2. **Yönlendirici** (`/api/oneri`): Jev açık ve hazırsa tür (7 tür) ve zorluk (basit/orta/zor) iki paralel Jev isteğiyle bulunur ve yanıtta `kaynak: "jev"` olur; öneri şeridinde ve Ayarlar → Yönlendirme'deki "Son sınıflandırma" satırında "Jev" yazar. Kapalı/hazır değil/hata → kural tabanlı, `kaynak: "kural"`. Tercih sırası her iki durumda da `yonlendirme.json`'dan gelir. Not: öneri yazarken (600 ms duraklamada) istenir, yani Jev açıkken her duraklama iki Jev isteği demektir.
3. **Yanıt puanlama** (Ayarlar → Jev → "Yanıtları Jev ile puanla", varsayılan **kapalı**): ortak sohbette bütün site yanıtları bitince arayüz `POST /api/yanit-puanla` `{sohbet, mesaj_sira}` çağırır. Sunucu kayıtlı yanıtlardan (en az iki) `Soru: …\nYanıtlar: [site: …] …` metnini kurar (soru en çok 600, her yanıt en çok 1500 karakter; toplam 4000 sınırına her yanıt sığacak biçimde eşit pay) ve Jev'e site adlarıyla sorar. Sonuç `{onerilen, site_ad, puan, olasiliklar}`; seçilen yanıta "Önerilen yanıt (Jev)" rozeti konur ve sonuç mesaja `jev_onerilen` olarak kaydedilir (sohbet yeniden açılınca rozet görünür). Ayar kapalıysa, Jev kapalıysa ya da Jev hata verirse 400 ve Türkçe sebep döner; rozet konmaz.

**Ayarlar → Jev**: "Jev açık" (varsayılan açık; kapalıyken Jev'e hiç istek gitmez), "Yanıtları Jev ile puanla", yukarıdaki uyarı metni ve durum: anahtar dosyası bulundu/bulunamadı, model, son çağrı (zaman, sonuç, Türkçe hata sebebi, toplam/başarılı/hatalı sayısı). `GET /api/jev-durum` bunları döner; anahtar değeri ve mesaj içeriği hiçbir yanıtta yoktur.

**Yapılandırma**: Hafıza OS kasasındaki `komuta/jev.json` (varsayılan `D:\YusufII\HAFIZAM1\kasa\komuta\jev.json`; `YZ_JEV_AYAR` ortam değişkeni bu dosyanın yolunu değiştirir). Kullanılan alanlar: `credentials_file` (anahtar dosyasının mutlak yolu), `provider` (`vercel` ya da `typesafe`), `model` (zorunlu), `base_url`, `mode` (`off` ise uygulama da Jev'i hiç çağırmaz), isteğe bağlı `allow_custom_endpoint`. Anahtar **yalnızca** `credentials_file` dosyasından okunur (Vercel: `{"AI_GATEWAY_API_KEY": "…"}`, TypeSafe: `{"TYPESAFE_API_KEY": "…"}`); ortam değişkenleri okunmaz. Model sürümü jev.json'dan sabitlenir; 'latest' kullanılmaz (varsayılan model yok, `model` alanı eksikse "jev.json içinde model belirtilmemiş" sebebiyle Jev hazır değil sayılır; `JEV_MODEL` gibi ortam değişkenleriyle geçersiz kılınamaz). Dosya yoksa ya da biçimi bozuksa Jev "hazır değil" sayılır ve uygulama kurallarla çalışır. Anahtar yalnızca bellekte ve istek başlığında kullanılır; hiçbir dosyaya, loga, duruma ya da hata metnine yazılmaz.

**Çağrı biçimi** (`jev.py`; kasadaki `araclar/jev_client.py` istemcisinin `choice` sorusuyla aynı): `POST <base_url>/v1/systemone` (`base_url` `/v1` ile bitiyorsa `<base_url>/systemone`), başlıklar `Authorization: Bearer <anahtar>` ve `Content-Type: application/json`, gövde `{"model", "state": {"text", "context"?}, "questions": {"secim": {"type": "choice", "instructions", "criteria": {seçenek: açıklama}}}}`; yanıt `{"answers": {"secim": {"type": "choice", "choice", "probabilities": {seçenek: olasılık}}}}`. Olasılıklar seçeneklerle birebir uyuşmalı, toplamı ~1 olmalı (Vercel'in iki ondalığa yuvarlaması için seçenek başına ±0,005 tolerans) ve seçim en olası seçenek olmalı; değilse yanıt kullanılmaz. `jev.sinifla(metin, secenekler, baglam="")` → `{"secim", "puan" (seçimin olasılığı), "olasiliklar"}` ya da Türkçe `JevHatasi`. Zaman aşımı 8 sn, metin 4000 karakterle kısaltılır, otomatik tekrar yok.

**Güvenlik**: anahtar yalnızca sağlayıcının resmi HTTPS sunucusuna (`vercel` → `ai-gateway.vercel.sh`, `typesafe` → `api.typesafe.ai`) ya da yerel bir ağ geçidine (localhost/127.0.0.1/::1; ortam vekili atlanır) gider; başka bir sunucu için `jev.json`'da açıkça `"allow_custom_endpoint": true` gerekir. Yönlendirme (3xx) izlenmez. Her çağrı yalnızca sayaç, zaman, sonuç ve Türkçe hata sebebiyle bellekte kaydedilir; mesaj ve yanıt içeriği kaydedilmez. Testler gerçek `jev.json`'a ve anahtara dokunmaz: `testler/_ortam.py` `YZ_JEV_AYAR`'ı var olmayan geçici bir yola yönlendirir; `testler/test_jev.py` geçici ayar/anahtar dosyası (sahte değer) ve 127.0.0.1'de sahte bir HTTP sunucusu kullanır.

## API sürümünü başlatma

`baslat-api.bat` dosyasına çift tıkla. Tarayıcıda `http://127.0.0.1:8765` açılır. Kapatmak için siyah pencerede Ctrl+C.

Gereken tek şey Python 3.9 veya üstü. Ek paket kurulmaz.

## İlk ayar: API anahtarları

Sağ üstteki **Ayarlar** düğmesinden her sağlayıcının anahtarını yapıştır. "Anahtar al" bağlantısı seni doğru sayfaya götürür.

| Sağlayıcı | Anahtar sayfası |
|---|---|
| OpenAI (GPT) | https://platform.openai.com/api-keys |
| Google Gemini | https://aistudio.google.com/apikey |
| Anthropic (Claude) | https://console.anthropic.com/settings/keys |

Önemli: ChatGPT Plus, Gemini Advanced ve Claude Pro abonelikleri API anahtarı yerine geçmez. API kullanımı ayrıca, kullandıkça ücretlendirilir. Gemini'nin ücretsiz bir kullanım kotası vardır.

Anahtarlar yalnızca bu bilgisayardaki `%LOCALAPPDATA%\YZMerkezi\ayarlar.json` dosyasında saklanır, tarayıcıya ya da GitHub'a gönderilmez. İstersen `OPENAI_API_KEY`, `GEMINI_API_KEY`, `ANTHROPIC_API_KEY` ortam değişkenlerini de kullanabilirsin.

## Yeni çıkan modeller

- **Model listesi her seferinde sağlayıcıdan canlı çekilir.** Yeni bir model yayınlandığı gün listede, en üstte görünür; uygulamayı güncellemen gerekmez.
- Listede henüz yoksa model seçiminde **"✎ Model adını elle yaz…"** ile kimliğini yazabilirsin.
- Yeni bir şirket ya da servis çıkarsa **Ayarlar → Yeni sağlayıcı ekle** ile adresini gir. Çoğu servis "OpenAI uyumlu" çalışır.
- Hazır gelen ek sağlayıcılar: xAI (Grok), DeepSeek, Mistral, Groq ve tek anahtarla yüzlerce modele erişim veren OpenRouter.

## Bilgisayardaki (yerel) modeller

Ollama, LM Studio, Jan, llama.cpp, vLLM, GPT4All veya Text Generation WebUI çalışıyorsa uygulama açılışta onları kendiliğinden bulur. Sonradan açtıysan **Yerel modelleri tara** düğmesine bas. Yerel modeller internet ve anahtar gerektirmez.

Örnek: https://ollama.com adresinden Ollama'yı kur, `ollama pull llama3.2` komutunu çalıştır, sonra **Yerel modelleri tara**.

## Güvenlik

Alınan önlemler:
- **Yalnızca yerel erişim**: iki sunucu da sadece `127.0.0.1` dinler; `Host` ve `Origin` başlıkları denetlenir (başka sitelerden ya da DNS yeniden bağlama saldırılarından gelen istekler 403 alır). Sunucular portu paylaşmaz: port başka bir program tarafından tutuluyorsa bağlanma hata verir.
- **İstek belirteci ve açılış kodu**: her açılışta rastgele bir belirteç üretilir ve yalnızca bellekte tutulur. Belirteç **Edge komut satırına girmez** (komut satırını aynı bilgisayardaki her süreç `Win32_Process` ile okuyabilir): sunucu tek kullanımlık, 30 sn geçerli bir açılış kodu üretir ve Edge `--app=http://127.0.0.1:PORT/ac/<kod>` ile açılır. `GET /ac/<kod>` kodu tüketir (ikinci kullanım ya da süresi dolmuş kod 403), belirteci `Set-Cookie: yz_oturum_<port>=…; HttpOnly; SameSite=Strict; Path=/` çerezine koyar ve `/` sayfasına 302 ile yönlendirir. Arayüz JavaScript'i belirteci hiç görmez (sessionStorage/adres parçası kullanılmaz). Her `/api/*` isteği (GET dahil) belirteci `X-YZ-Token` başlığında ya da bu çerezde taşımalıdır (çerez adı porta özgüdür; 127.0.0.1'deki başka bir portun çerezi kabul edilmez) (sabit zamanlı `hmac.compare_digest`); çerezle gelen istekte `Sec-Fetch-Site` başlığı varsa `same-origin` olmalıdır (başka siteden tetiklenen istek 403). Belirteçsiz/yanlış istek 403 alır. `#t=`/`?t=` içeren bir adres uygulama penceresi olarak açılmaz. İkinci örnek (`POST /api/pencere-ac`) de yeni bir açılış koduyla `/ac/<kod>` adresini açar. API sürümü (`sunucu.py`) de aynı yolu kullanır: varsayılan tarayıcıya (`webbrowser.open`) yalnızca `/ac/<kod>` gider; `--tarayici-acma` ile ekrana 5 dakika geçerli tek kullanımlık bir bağlantı yazılır. Masaüstü sürümü, ikinci kez açılışta çalışan örneğe pencere açabilmek için belirteci `%LOCALAPPDATA%\YZMerkezi\belirtec` dosyasına yazar (depoda değildir); port meşgulken önce `GET /api/kimlik` ile çalışan örneğin gerçekten bu uygulama olduğu doğrulanır, değilse hiçbir pencere açılmaz.
- **Güvenlik başlıkları**: tüm yanıtlarda `X-Frame-Options: DENY`, sıkı bir `Content-Security-Policy` (satır içi script/stil yok), `X-Content-Type-Options: nosniff`, `Referrer-Policy: no-referrer`, `Cross-Origin-Resource-Policy: same-origin`.
- **İstek sınırları**: gövde en çok 1 MB ve 10 sn'de okunur, JSON nesnesi olmalıdır. Beklenmeyen hatalarda arayüze yalnızca kısa bir kod gider; ayrıntı `%LOCALAPPDATA%\YZMerkezi\hata.log` dosyasına yazılır.
- **Allowlist'ler**: `/api/ayar` şemayla doğrulanır (bilinmeyen değerler reddedilir); masaüstü programı olarak yalnızca açık ve yerel sürücüdeki `.exe` dosyaları eklenebilir (ağ yolu, `.bat`, tarayıcılar reddedilir) ve her açılışta yol yeniden denetlenir; site adresleri yalnızca ilgili sitenin alan adına gidebilir. Çok hedefli ilk gönderimde "Şu hesaplara gidecek" onayı istenir (Ayarlar → Genel'den kapatılabilir).
- **Tarayıcı denetimi ağ portu olmadan**: Edge, `--remote-debugging-pipe` ile başlatılır; Chrome DevTools Protocol yalnızca uygulamanın kendisiyle Edge arasındaki iki anonim borudan (pipe) konuşulur. Hiçbir TCP portu dinlenmez (`netstat -ano` ile görülebilir); bu yüzden aynı bilgisayardaki başka bir program ya da bir web sayfası tarayıcıya bağlanıp oturum çerezlerini (`Network.getAllCookies`) okuyamaz. Boru yalnızca uygulamayı başlatan süreçte olduğundan, ikinci kez açılan `baslat.bat` bile tarayıcıya bağlanamaz; pencereyi çalışan uygulamaya belirteçli `POST /api/pencere-ac` isteğiyle açtırır. Uygulama kapanınca boru kapanır ve Edge de kapanır.
- **Jev'e gitmeden önce hassas tarama**: Jev'e giden her istek tek bir kapıdan geçer (`jev_guvenli_sinifla`): Jev'in ikinci görüşü (`/api/gonder` ön taraması ve `/api/sor`), yönlendirme sınıflandırması (`/api/oneri`, `/api/sor`) ve yanıt puanlama (`/api/yanit-puanla`, soru ve yanıtların tamamı). Gidecek metinlerin herhangi birinde (düşük önemli kişisel bilgi dahil) bulgu varsa Jev'e hiçbir şey gönderilmez, kural tabanlı/yerel yola düşülür ve durum "hassas içerik, Jev'e gönderilmedi" olur (`jev_notu` / `durum` alanı).
- **Hafıza bağlamı için onay**: kasadan seçilen bağlam motora ya da sitelere gitmeden önce gösterilir. `/api/sor` bağlam ekleyecekse akışı `{"tur": "baglam_onay", "baglam", "karakter", "baglam_kimligi"}` olayıyla durdurur (hiçbir şey gönderilmez, geçmişe yazılmaz); Gelişmiş `/api/gonder` aynı alanlarla `baglam_onay: true` döner. Arayüzde katlanabilir panel çıkar: **Ekleyerek gönder** (istek `baglam_karari: "ekle"` ve gösterilen bağlamın kimliğiyle tekrar gelir; yalnızca kullanıcının gördüğü bağlam eklenir, kimlik tek kullanımlık ve aynı mesaja bağlıdır), **Bağlamsız gönder** (`baglam_karari: "ekleme"`, hafıza aracı hiç çalıştırılmaz), **Vazgeç**. Ayar: Ayarlar → Hafıza → "Hafıza bağlamı için her seferinde onay iste" (varsayılan açık; kapalıysa bağlam sormadan eklenir).
- **hafiza.py bütünlük denetimi**: kasadaki `araclar/hafiza.py` ilk kez başarıyla çalıştırıldığında sha256 özeti `%LOCALAPPDATA%\YZMerkezi\hafiza-py.sha256` dosyasına yazılır. Sonra dosya değişmişse araç **çalıştırılmaz**, bağlam boş kalır, `GET /api/hafiza-durum` `hash_degisti: true` ve uyarı döner, Ayarlar → Hafıza'da "hafiza.py'nin yeni sürümünü onayla" düğmesi çıkar (`POST /api/hafiza-onayla` yeni özeti kabul eder).
- **Geçmiş maskeli kaydedilir**: sohbet geçmişine (ve Hafıza OS gelen kutusu adaylarına) yazılan kullanıcı ve asistan metinleri `hassas.maskele` ile kaydedilir: bulunan anahtar/parola/kimlik/IBAN/kart/olası anahtar değerleri `[GİZLİ:<kategori>]` olur (parola, bağlantı dizesi ve `Bearer` kalıplarında yalnızca değer). Motora/siteye giden metin maskelenmez (kullanıcı "Yine de gönder" dediyse ham gider). E-posta ve telefon maskelenmez.
- **Veri depoda değil**: API anahtarları (`ayarlar.json`), ayarlar ve sohbet geçmişi (`masaustu-ayarlar.json`), tarayıcı profili (oturum çerezleri), belirteç ve günlükler varsayılan olarak `%LOCALAPPDATA%\YZMerkezi` altındadır (proje klasöründe değil); eski kopyalar için `.gitignore` dışlaması da durur. Ayar dosyası bozulursa silinmez, `<ad>.bozuk-<zaman>.json` olarak saklanır. Testler gerçek ayar/profil dosyalarına dokunmaz (geçici klasör kullanır).

Kalan riskler:
- Aynı Windows kullanıcı hesabında çalışan bir zararlı yazılım belirteç dosyasını, ayar dosyalarını ve tarayıcı profilini (oturum çerezleri, Windows'un kullanıcıya bağlı şifrelemesiyle) okuyabilir ya da uygulamanın sürecine müdahale edebilir. Bu uygulama bunu engelleyemez; bilgisayarını güncel ve temiz tut.
- Site pencereleri açıkken oturumlar o profilde canlıdır: işin bitince uygulamayı ya da tarayıcı pencerelerini kapatabilirsin (oturum silinmez).
- Gemini için, kişisel Google hesabın yerine bu uygulamaya ayrılmış **ayrı bir Google hesabı** kullanmanı öneririz.
- Masaüstü programlarına gönderim pano ve tuş taklidiyle yapılır; gönderim sırasında panodaki metin geçici olarak değişir (sonra eski haline döner) ve fare/klavyeye dokunulmamalıdır.

Klasör izinleri için öneri (kendi kullanıcın, SYSTEM ve Yöneticiler dışındakilerin erişimini kapatır; komutu istersen yönetici olmayan bir komut isteminde kendin çalıştır, uygulama bunu yapmaz):

```
icacls "D:\YusufII\Projeler\yz-merkezi" /inheritance:r /grant:r "%USERNAME%:(OI)(CI)F" "SYSTEM:(OI)(CI)F" "Administrators:(OI)(CI)F"
```

### Kabul edilen riskler

- **Açılış kodu yarışı**: `/ac/<kod>` adresi 30 sn boyunca komut satırında görünür. Aynı hesaptaki yerel bir süreç kodu önce tüketirse arayüz açılmaz (tek kullanım) ve oturum çerezi o sürece gider. Kabul edildi: aynı kullanıcı hesabındaki zararlı yazılım zaten profil dosyalarına erişebilir.
- **hafiza.py ilk-güven penceresi (TOFU)**: ilk çalıştırmada görülen özet güvenilir sayılır; dosya ilk çalıştırmadan önce değiştirilmişse fark edilmez. Kabul edildi. Azaltma: kullanıcı Ayarlar → Hafıza'dan özeti görüp kasadaki git kaydıyla karşılaştırabilir. (Denetim ile çalıştırma arasındaki yarış kapatılmıştır: dosya tek seferde okunur, özet ve çalıştırılan kod aynı baytlardır.)
- **hafiza.py'nin kardeş modülleri**: `hafiza.py`'nin içe aktardığı kasa modülleri (`kasa/araclar/` altı) hash kapsamı dışındadır; yalnızca `hafiza.py` özetlenir. Kasa ACL'si dar olduğu için kabul edildi.

## Hafıza OS bağlantısı

Masaüstü sürümü, kişisel hafıza kasana (Hafıza OS, varsayılan `D:\YusufII\HAFIZAM1\kasa`; `YZ_KASA` ortam değişkeniyle değişir) bağlıdır; ChatGPT, Gemini ve Claude aynı hafızadan beslenir. Ayarlar → **Hafıza** bölümünde üç anahtar (üçü de varsayılan açık: bağlamı ekle, aday yaz, bağlam için her seferinde onay iste), kasanın yolu ve durum görünür. Bağlam onayı ve `hafiza.py` bütünlük denetimi için "Güvenlik" bölümüne bak.

Veri akışı:
1. **Okuma ("Hafızayı mesaja ekle")**: mesaj gönderilirken kasadaki `araclar/hafiza.py --vault . context "<mesaj>" --limit 5 --char-budget 1200 --local` yerel bir alt süreç olarak çalıştırılır (kasa klasörü çalışma klasörüdür, en çok 10 sn; `--local` ile Mem0 ve ağ kullanılmaz). Dönen bağlam mesajın başına `Bağlam (kişisel notlarımdan, yalnızca gerekiyorsa kullan):` başlığıyla eklenir ve `---` çizgisinden sonra senin mesajın gelir. **Eklenen bağlam, mesajı alan her siteye (işaretli hesaplara) gider**; yani kasadan seçilen satırlar o şirketlerin sunucularına ulaşır. İstemediğinde anahtarı kapat.
2. **Sır süzgeci**: dönen metinde `sk-`, `AIza`, `ghp_`, `-----BEGIN`, parola, şifre (ve password, API key benzeri) geçen satırlar atılır; yani sır benzeri kayıtlar siteye gitmez. Bağlam boşsa, araç hata verirse ya da zaman aşımına uğrarsa hiçbir şey eklenmez ve mesaj olduğu gibi gider (sebep Ayarlar → Hafıza durumunda görünür).
3. **Geçmiş**: yerel sohbet geçmişinde ham mesaj ve eklenen bağlam ayrı alanlarda tutulur; mesaj balonunun altında katlanabilir "Hafızadan eklenen bağlam (N karakter)" bölümü neyin gittiğini gösterir. "Yeniden gönder" ham mesajı yeniden gönderir (bağlam yeniden aranır).
4. **Yazma ("Yanıtları hafızaya aday olarak yaz")**: Hafıza OS'a (katalog, Mem0, `hafiza.py candidate-add` kuyruğu) doğrudan yazılmaz; o kuyruk kaynak dosyada aynen bulunan doğrulanmış gerçekler içindir, sohbet yanıtı özetleri bu koşulu taşımaz. Bunun yerine kasanın ham giriş klasörüne `gelen-kutusu/yz-merkezi/YYYY-MM-DD.md` dosyasına **yalnızca ekleme** yapılır (frontmatter: `kaynak: yz-merkezi`; her kayıt: zaman, site, soru özeti en çok 200, yanıt özeti en çok 600 karakter). Var olan dosya ve notlar silinmez, taşınmaz, yeniden adlandırılmaz, üzerine yazılmaz; soru ya da yanıtında sır benzeri içerik olan kayıt hiç yazılmaz; aynı kayıt iki kez yazılmaz. Bu kayıtlar onaylı bilgi değildir, kasanın kendi inceleme akışı değerlendirir.
5. **Durum**: `GET /api/hafiza-durum` yanıtı `{kasa_var, hafiza_py_var, son_mod, son_hata, hash_degisti, hash_uyarisi}` (ve arayüzde gösterilen `kasa` yolu) döner; `POST /api/hafiza-onayla` değişmiş `hafiza.py`'nin yeni özetini kabul eder.

Testler gerçek kasaya dokunmaz: `testler/_ortam.py` `YZ_KASA`'yı var olmayan geçici bir yola yönlendirir, `test_hafiza_kopru.py` geçici bir kasa ve sahte `araclar/hafiza.py` kurar.

## Motorlar (ayrıntı)

### Özet

`motorlar/` paketi, uygulamanın tek pencerede "tek yapay zeka gibi" çalışmasını sağlar. Claude Code, Codex CLI
ve Gemini CLI arka planda, **kullanıcının kendi hesabıyla** ve **pencere açmadan** (`CREATE_NO_WINDOW`)
çalıştırılır. Yanıt satır satır okunup olay olarak akıtılır. Yalnızca standart kütüphane kullanılır. Testler
sahte motorlarla çalışır, gerçek CLI'lara istem göndermez.

### Arayüz

```python
from motorlar import MOTORLAR, motor, MotorHatasi
m = motor("claude")          # "claude" | "codex" | "gemini"
m.hazir_mi()                 # {"hazir": bool, "sebep": str, "surum": str|None, "giris": bool|None}  (60 sn önbellek)
m.modeller()                 # [{"id", "ad", "sinif": "hizli"|"dengeli"|"guclu"}]
for olay in m.sor(istem, oturum=None, model=None, sistem=None, calisma_klasoru=None, iptal=threading.Event()):
    ...
```

Olaylar (sırayla):

| tur | alanlar | not |
|---|---|---|
| `durum` | `metin` | İlk olay her zaman `"düşünüyor…"`. Arka arkaya gelen aynı durum bastırılır. |
| `baslangic` | `oturum` | Tam bir kez, ilk `parca`dan önce gelir. |
| `parca` | `metin` | Yanıt parçası. |
| `bitti` | `oturum`, `metin` (tam yanıt), `model`, `sure` (sn) | Başarılı bitiş. |
| `hata` | `mesaj` (Türkçe) | İptalde ayrıca `iptal: True`. Gemini girişi yoksa ayrıca `giris_gerekli: True`. |

- `oturum`: motorun kendi oturum kimliğidir (Claude `session_id`, Codex `thread_id`, Gemini `session_id`).
  Sonraki `sor(..., oturum=...)` çağrısında aynı konuşma sürdürülür. Kimlik alınamazsa `None` döner. O durumda
  sunucu geçmişi istemin içinde göndermelidir.
- **Zaman aşımı:** ilk çıktı satırı için 60 sn, toplam süre için 600 sn. Örnekteki `ilk_bayt_zaman_asimi` ve
  `toplam_zaman_asimi` öznitelikleriyle değiştirilebilir.
- **İptal:** `iptal` olayı kurulunca süreç ağacı durdurulur (Windows'ta `taskkill /T /F`, sonra `terminate`).
  Generator erken kapatıldığında (`close()`, çöp toplama) da süreç durdurulur.
- **Hata mesajı:** stderr toplanır. Süreç yanıtı tamamlamadan biterse ilk 300 karakteri mesaja eklenir.
- **Girdi:** İstem komut satırına değil **standart girdiye** yazılır. Böylece uzun geçmiş ve `& | % "` gibi özel
  karakterler güvenle geçer.
- **Kodlama:** Alt süreç `encoding="utf-8", errors="replace"` ile okunur.
- **Çalışma klasörü:** varsayılan `%LOCALAPPDATA%\YZMerkezi\calisma` (`guvenlik.veri_yolu`). `YZ_MOTOR_CALISMA`
  ile değiştirilebilir, klasör yoksa oluşturulur.
- **Yürütülebilir dosya:** `YZ_MOTOR_CLAUDE_EXE`, `YZ_MOTOR_CODEX_EXE`, `YZ_MOTOR_GEMINI_EXE` ile değiştirilebilir.
  `.py` bu Python ile, `.js` node ile çalıştırılır. `.cmd`/`.bat` reddedilir, çünkü kullanıcı metni cmd.exe'den
  geçmemelidir.

### Claude Code

- **Gereksinim:** Claude Code (`%USERPROFILE%\.local\bin\claude.exe`, yoksa PATH). Denenen sürüm: 2.1.296.
- **Giriş:** Terminalde `claude` çalıştırıp `/login` ile ya da `claude auth login` ile giriş yapılır.
  `hazir_mi()`, `claude auth status` JSON'undaki `loggedIn` değerine bakar.
- **Komut:**
  `claude -p --output-format stream-json --verbose --include-partial-messages --permission-mode dontAsk --strict-mcp-config --setting-sources project,local [--model M] [--resume OTURUM] --append-system-prompt "<sistem>" --tools ""`
- **Ayrıştırma:**
  - `system/init` olayından `session_id` ve model alınır.
  - `stream_event` → `content_block_delta/text_delta` olayları parça olur. `thinking_delta` durum olarak işlenir.
  - `assistant` iletisi yalnızca kısmi parça gelmediyse kullanılır.
  - `result` olayından tam metin ve oturum alınır. `is_error` hata olarak işlenir.
- **Sınırlar:**
  - `--bare` kullanılmaz, çünkü abonelik girişini okumaz.
  - Araçlar kapalıdır (`--tools ""`) ve MCP sunucuları yüklenmez.
  - Kullanıcı ayarları (`~/.claude/settings.json`) yüklenmez, böylece kancalar (hook) sohbet sırasında çalışmaz.
    Bu bilinçli bir seçimdir: `AYAR_KAYNAKLARI`.
  - `ANTHROPIC_API_KEY` ortamda tanımlıysa Claude Code aboneliği değil API anahtarını (ücretli) kullanabilir.
  - Model takma adları: `haiku` (hızlı), `sonnet` (dengeli), `opus` (güçlü).

### Codex CLI

- **Gereksinim:** `%LOCALAPPDATA%\OpenAI\Codex\bin\*\codex.exe` dosyalarından değiştirilme zamanı en yeni olan.
  Bulunamazsa PATH'teki `codex.exe` kullanılır. Denenen sürüm: 0.162.0-alpha.17.2.
- **Giriş:** `codex login` (ChatGPT hesabı). `hazir_mi()`, `codex login status` çıktısına bakar.
- **Komut:**
  - Yeni konuşma: `codex exec --json --skip-git-repo-check --sandbox read-only [-m M] -`
  - Devam: `codex exec resume --json --skip-git-repo-check -c sandbox_mode="read-only" [-m M] THREAD_ID -`
  - `exec resume` alt komutunda `--sandbox` seçeneği olmadığı için aynı ayar `-c` ile verilir. Bu, `--help` ile
    doğrulandı.
- **Ayrıştırma:**
  - `thread.started` olayından oturum alınır.
  - `item.*` içindeki `agent_message` metni artımlı olarak parçaya dönüşür. Birden çok ileti boş satırla ayrılır.
  - `reasoning` "düşünüyor…" durumu olur. Komut, MCP, web ve dosya öğeleri "araç kullanıyor…" durumu olur.
  - `turn.completed` bitiş, `turn.failed` hata demektir.
  - `error` olayları geçici olabileceği için (yeniden bağlanma) yalnızca uyarı olarak işlenir. Tur tamamlanmazsa
    hata mesajı olur.
- **Sistem istemi:** Codex'te sistem istemi bayrağı yoktur. Talimat istemin başına `[Talimat]…[/Talimat]` olarak eklenir.
- **Modeller:** Codex'in kendi önbelleğinden (`~/.codex/models_cache.json`, `visibility=list`) okunur. Sınıf,
  açıklamadaki "fast/affordable" → hızlı, "frontier" → güçlü kuralıyla belirlenir. Önbellek okunamazsa sabit liste
  kullanılır: gpt-6-luna, gpt-6.1-sol, gpt-6-astra. Olaylarda model adı olmadığı için `bitti.model`,
  `config.toml` içindeki varsayılan modeldir.

### Gemini CLI

- **Gereksinim:** `npm install -g @google/gemini-cli` (bu makinede kuruldu: 0.64.0, npm öneki `D:\n8n\nodejs`).
  Doğrudan `node.exe` + `node_modules\@google\gemini-cli\bundle\gemini.js` çalıştırılır, `gemini.cmd` çağrılmaz.
- **Giriş:** Terminalde `gemini` çalıştırılıp Google hesabıyla (tarayıcı OAuth) giriş yapılır. Uygulama bunu
  kendisi yapmaz. `hazir_mi()` ağa çıkmadan şunlara bakar:
  - `~/.gemini/oauth_creds.json` ya da `gemini-credentials.json` dosyası,
  - ya da `GEMINI_API_KEY`/`GOOGLE_API_KEY` ortam değişkeni.

  Giriş yoksa `sor()` hiç süreç başlatmaz ve "Giriş gerekli: terminalde `gemini` çalıştırıp Google hesabınla giriş
  yap." hatasını döndürür. Böylece başsız OAuth akışı bir tarayıcı penceresi açmaz.
- **Komut:** İstem standart girdiden verilir. stdin/stdout boru olduğu için CLI başsız çalışır, `-p` gerekmez.
  `gemini.js --output-format stream-json --skip-trust --approval-mode default [-m M] [--resume OTURUM]`
- **Ortam değişkenleri:**
  - `GEMINI_CLI_TRUST_WORKSPACE=true`: güvenilmeyen klasörde başsız çalışma reddini önler.
  - `NO_BROWSER=true`: tarayıcı açılmaz.
  - `GEMINI_CLI_NO_RELAUNCH=true`: ikinci bir node süreci açılmaz, iptal temiz olur.
- **Güvenilir klasör:** `--skip-trust` ve `GEMINI_CLI_TRUST_WORKSPACE=true` birlikte kullanılır. Bu seçenekler
  CLI'nin "trusted directory" hata metninde önerilir.
- **Ayrıştırma:** stream-json şeması 0.64.0 paket kaynağından doğrulandı.
  - `init{session_id, model}`
  - `message{role:"assistant", content, delta:true}` → parça
  - `tool_use`/`tool_result` → durum
  - `error{severity, message}`
  - `result{status:"success"|"error", error?, stats}`
- **Oturum:** `--resume` tam UUID kabul eder (paket kaynağında doğrulandı). Oturumlar çalışma klasörü (proje)
  başına saklanır. Devam ettirmek için aynı `calisma_klasoru` kullanılmalıdır.
- **Sınırlar:**
  - `--approval-mode default` kullanılır, `--yolo` yoktur. Başsız modda onay gerektiren araçlar çalışmaz.
  - Sistem istemi bayrağı yoktur, talimat istemin başına eklenir.
  - Model listesi sabittir: gemini-2.5-flash-lite, gemini-2.5-flash, gemini-2.5-pro.
- **Çıkış kodları:** 41 → giriş gerekli, 42 → geçersiz girdi, 55 ya da "trusted directory" → güven hatası.

### Testler

`testler/test_motorlar.py` dosyası `testler/sahte_motorlar/` altındaki sahte betikleri kullanır. Bu betikler
gerçek JSONL/stream-json biçimini basar. Senaryo, istemdeki anahtar sözcükle seçilir:

| Anahtar sözcük | Davranış |
|---|---|
| `HATA` | Motorun hata olayı |
| `COKME` | stderr'e yazar ve tamamlanmadan çıkar |
| `SESSIZ` | Hiç çıktı vermez (ilk bayt zaman aşımı) |
| `YAVAS` | Yavaş akış (iptal ve toplam zaman aşımı) |

Gerçek CLI'larda yalnızca `--version` ve giriş durumu denetlenir. İstem göndermek ücret ve kota harcadığı için
kullanıcı onayı gerekir.

## Güncelleme ve temizlik

**Kural:** yeni sürüm kurulunca uygulama eski sürümden kalan dosyaları kendisi siler; kullanıcı verisine asla dokunmaz. Sürüm `surum.py` içindedir (`SURUM = "1.1.0"`, semver) ve `GET /api/kimlik` → `{"uygulama": "yz-merkezi", "surum": ...}` ile görünür; Ayarlar → Hakkında sürümü ve güncelleme durumunu gösterir.

**Kurulum düzeni** (`guncelleme.py`):

- `<kurulum kökü>/surumler/<sürüm>/`: her sürüm kendi klasöründe, kendi `manifest.json` dosyasıyla (`{"surum", "olusturma", "dosyalar": [{"yol", "sha256", "boyut"}]}`).
- `<kurulum kökü>/guncel.json`: etkin sürüm işaretçisi `{"surum": "1.1.0", "yol": "surumler/1.1.0"}`. `baslat.bat` (ve `kisayol-olustur.ps1` ile kurulan kısayol) bu dosya varsa `guncelleme.py --baslat` ile oradaki sürümü, yoksa kökü çalıştırır.
- Manifeste yalnızca uygulama dosyaları girer: kökteki `.py/.json/.bat/.ps1/.md` ile `arayuz/`, `arayuz-masaustu/`, `motorlar/`, `araclar/`. `.git`, `testler/`, `__pycache__`, `surumler/` ve veri dosyaları hariçtir. Üretmek için `python araclar\manifest_uret.py`.
- Yerel kurulum/güncelleme: `surum.py` içinde `SURUM`'u artır, sonra `python araclar\surum_paketle.py` (kökten `surumler/<SURUM>/` içine manifestle kopyalar ve aşağıdaki güncelleme adımlarını çalıştırır). Aynı sürüm numarasıyla farklı içerik kurulmaz: hedef klasör varsa ve manifesti kaynaktan farklıysa güncelleme "Aynı sürüm numarası farklı içerikle zaten kurulu; önce SURUM'u artırın" hatasıyla reddedilir (hiçbir şey değişmez). Başka bir klasördeki hazır sürüm için: `python guncelleme.py --guncelle <klasör>`.

**Güncelleme sırası** (`guncelle(kurulum_koku, yeni_surum_klasoru)`):

1. Yeni sürümün manifestteki dosyaları `surumler/<sürüm>/` içine kopyalanır (klasör zaten varsa ve içeriği aynıysa kopyalama atlanır; içerik farklıysa güncelleme reddedilir).
2. **Doğrulama:** manifestteki her dosya var, boyut ve sha256 eşleşiyor, manifest dışı fazla dosya yok, hiçbir yerde symlink/junction yok. Sonra **duman testi:** ayrı bir süreçte `masaustu_sunucu`, `motorlar` ve `surum` içe aktarılır (önbellek yazılmaz).
3. Biri başarısızsa yalnızca bu işlemin kopyaladığı dosyalar geri alınır; **eski sürüm ve `guncel.json` olduğu gibi kalır** (zaten var olan bir klasöre dokunulmaz).
4. `guncel.json` atomik yazılır (geçici dosya + fsync + yerine koyma).
5. Eski sürümler temizlenir (`eski_surumleri_temizle`); **bir önceki sürüm saklanır**: etkin sürüm ve kalan manifestli sürümlerden semver sırasında en yeni olanı bırakılır, daha eskileri temizlenir.

**Geri alma:** `python guncelleme.py --geri-al` işaretçiyi etkin sürümden küçük en yeni sürüme çevirir; o sürüm önce manifestine göre doğrulanır ve duman testinden geçer, biri başarısızsa `guncel.json` değişmez. Hiçbir dosya silinmez (yeni sürüm de yerinde kalır).

**Bütünlük ve imza:** `--guncelle` yalnızca **yerel** bir klasördeki sürümün bütünlüğünü (manifestteki sha256, boyut, eksik/fazla dosya) doğrular; manifest imzalı değildir, yani manifesti değiştirebilen biri dosyaları da değiştirebilir. İnternetten otomatik indirme eklenirse **imzalı manifest zorunludur** (ör. Ed25519 imzası, açık anahtar uygulamaya gömülü; imzası doğrulanmayan sürüm kurulmaz).

**Temizliğin sınırları:**

- Yalnızca `surumler/<eski sürüm>/` altındaki ve **o klasörün kendi manifestinde** yazan dosyalar (ve onların `__pycache__` önbelleği) silinir; boş kalan klasörler kaldırılır. Silmeden önce her dosyanın sha256'sı manifestle karşılaştırılır; **uyuşmayan (sonradan değiştirilmiş) dosya atlanır** ve günlüğe yazılır.
- Silme **Windows geri dönüşüm kutusuna** yapılır (`SHFileOperationW`, `FO_DELETE | FOF_ALLOWUNDO | FOF_NO_UI`, yalnızca sabit disklerde). Taşınamazsa dosya **kalıcı silinmez**, atlanır ve günlüğe yazılır. Manifest dışı dosyalara, manifesti olmayan ya da manifesti geçersiz sürüm klasörlerine, etkin sürüme ve kurulum kökünün kendi dosyalarına dokunulmaz.
- Gerçek yol denetlenir: manifest yolu mutlaksa, sürücü içeriyorsa ya da `..` içeriyorsa o sürümün manifestinin **tamamı** reddedilir; gerçek yolu sürüm klasörünün dışına çıkan dosya atlanır. **Symlink ve junction (reparse point) asla izlenmez:** sürüm klasörü ya da yolun herhangi bir parçası bağlantıysa atlanır ve raporlanır.
- Sabit korunan kalıplar her durumda silinmez (manifestte geçse bile manifest reddedilir): `ayarlar*.json`, `masaustu-ayarlar*.json`, `*.bozuk-*.json`, `*.log`, `.tarayici-profili*`, `tarayici-profili*`, `veri`, `kasa`, `belirtec`, `guncel.json`, `.git`. Veri klasörü (`%LOCALAPPDATA%\YZMerkezi`: ayarlar, sohbet geçmişi, profil, günlükler) hiçbir zaman silinmez; kasa (Hafıza OS) hiç işlenmez.
- `.git` bulunan kök **geliştirme kurulumudur**: kökteki dosyalar hiçbir zaman silinmez, yalnızca `surumler/` düzeni işlenir. `.git` içeren bir sürüm klasörüne de dokunulmaz.
- Silinemeyen dosya kalırsa o sürümün `manifest.json` dosyası bir sonraki temizlik için bırakılır.

Her adım (kopyalama, doğrulama, duman testi, işaretçi, her silinen/atlanan dosya, geri alma) `%LOCALAPPDATA%\YZMerkezi\guncelleme.log` dosyasına yazılır (`YZ_GUNCELLEME_LOG` ile değiştirilebilir). `GET /api/guncelleme-durum` → `{surum, calisan_klasor, kurulum_koku, gelistirme_kurulumu, guncel, kurulu_surumler, gunluk}` (günlüğün son 20 satırı). Komut satırı: `python guncelleme.py --durum | --temizle | --geri-al | --yol`. Testler: `testler/test_guncelleme.py` (tamamı geçici klasörlerde).

## Klasör yapısı

- `motorlar/`: Claude, Codex ve Gemini komut satırı araçlarını saran motor paketi (`MOTORLAR`, `motor(id)`; `hazir_mi`, `modeller`, `sor`); Tek Asistan bunları çağırır
- `arayuz-masaustu/markdown.js` (güvenli Markdown → DOM), `uygulama.js` (Tek Asistan arayüzü), `gelismis.js` (eski çoklu pencere bölümü)
- `masaustu_sunucu.py`: masaüstü sürümünün arka ucu (Tek Asistan: `/api/sor`, `/api/durdur`, motor durumları; eski site/program uçları) (site durumu, sohbet listesi, gönderme, yanıt okuma, dizme; yedek olarak masaüstü programları)
- `arayuz-masaustu/`: masaüstü sürümünün Claude düzenindeki Türkçe arayüzü
- `pencereler.py`: Windows pencerelerini bulma, dizme ve yazı gönderme
- `tarayici.py`: Edge'i CDP borusuyla (ağ portu yok) ve ayrı profille (`%LOCALAPPDATA%\YZMerkezi\tarayici-profili`) başlatır; site sekmelerini bulur, pencere açar/dizer
- `cdp.py`: Edge'i Chrome DevTools Protocol ile anonim borular üzerinden denetleyen küçük istemci (`BoruBaglantisi`, sekme oturumu `Oturum`; yalnızca standart kütüphane)
- `siteler.py`: ChatGPT, Gemini ve Claude sitelerinin seçicileri ve sayfada çalışan JS parçaları (giriş denetimi, sohbet listesi, mesajlar, gönderme, yanıt)
- `hassas.py`: gönderme öncesi hassas bilgi taraması (API anahtarı, T.C. kimlik, IBAN/kart, parola; kural tabanlı)
- `yonlendirici.py` ve `yonlendirme.json`: mesajı sınıflandırıp site/model önerir; tercih sırası `yonlendirme.json` dosyasında düzenlenir
- `jev.py`: Jev (TypeSafe karar modeli) istemcisi; hassas bilgi uyarısı, yönlendirme ve yanıt puanlamada kullanılır, kurallar yedektir (yalnızca standart kütüphane)
- `uygulamalar.json`: tanınan masaüstü programları (ChatGPT, Gemini, Claude)
- `surum.py`: uygulama sürümü (semver) ve `/api/kimlik` yanıtı; `guncelleme.py`: sürüm kurma, doğrulama ve eski sürüm dosyalarını manifestle temizleme; `araclar/manifest_uret.py`, `araclar/surum_paketle.py`: manifest üretme ve kökten `surumler/<SURUM>/` kurma
- `guvenlik.py`: iki sunucunun ortak güvenlik yardımcıları (başlıklar, istek belirteci, gövde sınırı, hata günlüğü, ayar dosyası yazma/yedekleme)
- `hafiza_kopru.py`: Hafıza OS köprüsü (kasadaki `hafiza.py context` çağrısı, sır süzgeci, gelen kutusuna aday kayıt ekleme; yalnızca standart kütüphane)
- `sunucu.py`: API sürümünün yerel sunucusu ve sağlayıcı bağdaştırıcıları (OpenAI uyumlu, Anthropic, Gemini)
- `saglayicilar.json`: hazır sağlayıcı listesi; yeni bir satır eklemek yeni sağlayıcı demek
- `araclar/simge_uret.py`: simgeyi (SVG -> PNG -> ICO) yeniden üretir; `kisayol-olustur.ps1`: Masaüstü kısayolunu oluşturur
- `arayuz/`: Türkçe arayüz (HTML, CSS, JavaScript)
- `testler/`: otomatik testler, `python -m unittest discover testler` ile çalışır. `test_entegrasyon.py` gerçek Edge'i geçici profille açıp `sahte-site.html` (ChatGPT'yi taklit eden yerel sayfa ve `sahte-site.js`/`.css` dosyaları, yalnızca `YZ_TEST=1` iken sunulur) üzerinde uçtan uca dener; Edge yoksa atlanır, gerçek sitelere hiç bağlanmaz. `testler/_ortam.py` testlerde ayar dosyası, profil ve veri klasörünü geçici yollara yönlendirir (gerçek dosyalara ve gerçek `%LOCALAPPDATA%\YZMerkezi` klasörüne dokunulmaz)

## Yapay zekalar için notlar

Bu projenin metin dosyalarında (py, js, html, css, bat, ps1, md) dosyanın başında şu açıklama bulunur:

> Bu dosya Yusuf'a (yusufbesir) ait Yapay Zeka Merkezi projesinin parçasıdır.
> Yapay zeka ajanları bu dosyayı Yusuf'un kuralları çerçevesinde inceleyip değiştirebilir; silme kararı yalnız Yusuf'undur
> ve silme yalnızca Geri Dönüşüm Kutusu'na taşıyarak yapılır, kalıcı silme yoktur.
> Kurallar: BENIOKU.md (Yapay zekalar için notlar) ve D:\YusufII\HAFIZAM1\kasa\ORTAK-AJAN-KURALLARI.md.

Metin olmayan dosyalar (json, png, ico, svg) yorum satırı taşıyamadığı için aynı kurala bu BENIOKU.md üzerinden tabidir: `saglayicilar.json`, `uygulamalar.json`, `yonlendirme.json`, `arayuz/simge.ico`, `arayuz/simge.svg`, `arayuz-masaustu/simge.ico`, `arayuz-masaustu/simge.svg`, `arayuz-masaustu/simge-kucuk.svg`, `arayuz-masaustu/simge-256.png`.

Yapay zekalar bunları Yusuf'un kuralları çerçevesinde değiştirebilir; silme kararı yalnız Yusuf'undur ve yalnızca Geri Dönüşüm Kutusu'na taşınarak yapılır.

---
## Arşiv notu (2026-10-21)
Bu proje arşivlendi; AgentMom projesine devredildi. Uygulama dosyaları depodan kaldırıldı, notlar ve araştırmalar kaldı. Son çalışan sürüm `arsiv-son-calisir-kod` dalındadır (`git checkout arsiv-son-calisir-kod`). Yusuf'un kararıyla, 2026-10-21.
