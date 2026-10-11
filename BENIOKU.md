# Yapay Zeka Merkezi

GPT, Gemini, Claude ve bilgisayarındaki yerel modelleri tek ekranda, yan yana kullanmanı sağlayan Türkçe uygulama. Bir mesaj yazarsın, işaretli bütün pencerelere aynı anda gider ve yanıtları karşılaştırırsın.

İki sürümü var:

1. **Masaüstü sürümü (`baslat.bat`)**: ChatGPT, Gemini ve Claude web sitelerini kendi tarayıcı profilinde açıp birleştirir (bilgisayarda kurulu masaüstü programları yedek yol). API anahtarı gerekmez, kendi hesapların ve aboneliklerin kullanılır.
2. **API sürümü (`baslat-api.bat`)**: tarayıcıda çalışır, API anahtarlarıyla bağlanır.

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

Gönder'e basınca (Enter ya da ok) mesaj, siteye gitmeden önce taranır. Şu kalıplar aranır:
- **API anahtarı**: `sk-…` (16+ karakter), `sk-ant-…`, `sk-proj-…`, `AIza…` (30+), `ghp_…` (30+), `xoxb-…` ve `-----BEGIN … PRIVATE KEY` başlığı.
- **Kimlik**: 11 haneli T.C. kimlik kalıbı; rastgele 11 haneli sayılar uyarı çıkarmasın diye algoritma denetimlidir (ilk hane 0 olamaz, 10. ve 11. hane kuralı).
- **Finansal**: `TR` IBAN kalıbı ve 16 haneli kart numarası (boşluklu ya da tireli; Luhn sağlaması geçmeyen diziler kart sayılmaz).
- **Parola**: `parola`, `şifre`, `password`, `pin` + `:` ya da `=` + değer (aynı satırda) ve `eposta:parola` çifti.

Bir şey bulunursa mesaj **gönderilmez** ve yazı kutusunun üstünde bir şerit çıkar: "Bu mesaj <bir API anahtarı / bir parola / bir T.C. kimlik numarası / bir IBAN ya da kart numarası> içeriyor olabilir. **Yine de gönder** / **Vazgeç**". "Yine de gönder" aynı mesajı `onayli: true` ile yeniden yollar; şerit görünürken metni değiştirirsen şerit kapanır ve yeni metin yeniden denetlenir. Birden çok kategori varsa şu öncelik kullanılır: API anahtarı, parola, kimlik, finansal. Sunucu (`POST /api/gonder`) uyarı gerekiyorsa hiçbir yere yazmadan `{"onay_gerekli": true, "kategori", "aciklama"}` döndürür (HTTP 200). Anahtar: **Ayarlar → Genel → "Göndermeden önce hassas bilgi uyarısı"** (varsayılan açık). Tarama bir güvenlik ağıdır, kusursuz değildir: kalıba uymayan bir sırrı (örneğin kelimelerle yazılmış bir parolayı) yakalayamaz.

### Ajan seçimi (yönlendirici)

Yazarken (600 ms duraklayınca) mesaj kurallarla sınıflandırılır ve yazı kutusunun üstünde bir öneri şeridi çıkar: "Önerilen: Gemini · <model> (basit · araştırma) — **Uygula** / **Değiştir**".
- **Tür**: `kod` (kod bloğu ya da fonksiyon/hata/python/javascript/sql), `ceviri` (çevir/translate/ingilizce/türkçeye), `ozet` (özetle/kısaca), `arastirma` (araştır/karşılaştır/kaynak/neden), `yazi` (yaz/taslak/mail/makale), `matematik` (sayısal ifade ya da denklem), değilse `sohbet`. Birden çok kural uyarsa bu sıradaki ilki kazanır.
- **Zorluk**: uzunluk (200 karakterden kısa `basit`, 1200'den kısa `orta`, üstü `zor`); "ayrıntılı, kapsamlı, analiz, mimari, strateji, plan" geçerse +1 kademe, çok adımlı istek ("önce … sonra" ya da 3+ madde) +1 kademe (en çok `zor`).
- **Uygula**: yalnızca önerilen siteyi hedef yapar ve gönderim isteğine `model_sec: {"site", "model"}` ekler; sunucu mesajı yazmadan önce sitenin model menüsünden o modeli seçer. Seçilemezse (menü değişmiş, model yok, desteği henüz yok) mesaj **mevcut modelle yine gider** ve sorunlara "model seçilemedi: <sebep>" eklenir. Gönderince hedef seçimin eski haline döner. **Değiştir**: sıradaki öneriye geçer. Bir site sohbeti açıkken şerit çıkmaz.
- **Otomatik yönlendirme** (Ayarlar → Genel, varsayılan **kapalı**): açıkken öneri kendiliğinden uygulanır; şerit yine görünür ("Otomatik seçildi: …") ve Değiştir ile başka öneriye geçebilirsin.
- **Model adı**: kurallarda tam model kimliği yazılmaz, yalnızca ad parçası yazılır (ör. `flash`, `sonnet`, `gpt`). Gerçek model, ilgili sitenin canlı model menüsünden (`GET /api/modeller?site=`, 60 sn önbellekli; site açık ve giriş yapılmışsa) büyük/küçük harf duyarsız "içerir" eşleşmesiyle bulunur; ilk eşleşen alınır. Menü okunamazsa ya da eşleşme yoksa yalnızca site önerilir ve sebebi şeritte yazar. Yeni bir sürümü hedeflemek için parçayı uzat (ör. `sonnet 5.5`).
- Sunucu uçları: `POST /api/oneri` `{metin}` → `{tur, zorluk, oneriler: [{site, model_icerir, model, sebep}], kaynak: "kural" | "jev"}`; `GET /api/yonlendirme` (kural tablosu, dosya yolu, son sınıflandırma; mesaj metni içermez); `POST /api/yonlendirme-ac` (kural dosyasını varsayılan düzenleyicide açar).

### Kuralları düzenleme: `yonlendirme.json`

Tercih sırası proje klasöründeki `yonlendirme.json` dosyasındadır (Ayarlar → Yönlendirme sekmesinde yolu, salt okunur tablosu, son sınıflandırma sonucu ve "yonlendirme.json dosyasını aç" düğmesi vardır). JSON'da yorum satırı olmadığı için açıklama burada:

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
- Testlerde başka bir dosya kullanmak için `YZ_YONLENDIRME` ortam değişkeni yolu değiştirir.

## Jev

Jev, TypeSafe AI'ın karar (sınıflandırma) modelidir. Uygulama onu üç yerde kullanır; her yerde kural tabanlı yol **yedek** olarak kalır. **Mesajların ve seçtiğin durumlarda yanıtların TypeSafe'in uzak Jev sunucusuna gider (Yusuf'un onayıyla). Yeni bir Jev sürümü ya da yerel seçenek çıkınca yeniden değerlendirilecek.** Jev dışında hiçbir uzak servise veri gönderilmez.

1. **Hassas bilgi uyarısı**: önce yerel tarama (`hassas.tara`). Yerel tarama bir şey bulamazsa ve Jev açıksa metin Jev'e "parola / api_anahtari / kimlik_bilgisi / finansal / yok" seçenekleriyle sorulur. Jev "yok" dışında bir şey seçer ve o seçeneğin olasılığı **≥ 0,6** ise aynı onay şeridi çıkar (`onay_gerekli`, `kaynak: "jev"`, açıklamada "Jev'in değerlendirmesine göre"). Yerel tarama bir şey bulduysa, kullanıcı "Yine de gönder" dediyse ya da uyarı kapalıysa Jev'e sorulmaz. Jev hata verirse sessizce yerel sonuç geçerlidir. Jev sorusu ayar kilidi dışında yapılır (en çok 8 sn).
2. **Yönlendirici** (`/api/oneri`): Jev açık ve hazırsa tür (7 tür) ve zorluk (basit/orta/zor) iki paralel Jev isteğiyle bulunur ve yanıtta `kaynak: "jev"` olur; öneri şeridinde ve Ayarlar → Yönlendirme'deki "Son sınıflandırma" satırında "Jev" yazar. Kapalı/hazır değil/hata → kural tabanlı, `kaynak: "kural"`. Tercih sırası her iki durumda da `yonlendirme.json`'dan gelir. Not: öneri yazarken (600 ms duraklamada) istenir, yani Jev açıkken her duraklama iki Jev isteği demektir.
3. **Yanıt puanlama** (Ayarlar → Jev → "Yanıtları Jev ile puanla", varsayılan **kapalı**): ortak sohbette bütün site yanıtları bitince arayüz `POST /api/yanit-puanla` `{sohbet, mesaj_sira}` çağırır. Sunucu kayıtlı yanıtlardan (en az iki) `Soru: …\nYanıtlar: [site: …] …` metnini kurar (soru en çok 600, her yanıt en çok 1500 karakter; toplam 4000 sınırına her yanıt sığacak biçimde eşit pay) ve Jev'e site adlarıyla sorar. Sonuç `{onerilen, site_ad, puan, olasiliklar}`; seçilen yanıta "Önerilen yanıt (Jev)" rozeti konur ve sonuç mesaja `jev_onerilen` olarak kaydedilir (sohbet yeniden açılınca rozet görünür). Ayar kapalıysa, Jev kapalıysa ya da Jev hata verirse 400 ve Türkçe sebep döner; rozet konmaz.

**Ayarlar → Jev**: "Jev açık" (varsayılan açık; kapalıyken Jev'e hiç istek gitmez), "Yanıtları Jev ile puanla", yukarıdaki uyarı metni ve durum: anahtar dosyası bulundu/bulunamadı, model, son çağrı (zaman, sonuç, Türkçe hata sebebi, toplam/başarılı/hatalı sayısı). `GET /api/jev-durum` bunları döner; anahtar değeri ve mesaj içeriği hiçbir yanıtta yoktur.

**Yapılandırma**: Hafıza OS kasasındaki `komuta/jev.json` (varsayılan `D:\YusufII\HAFIZAM1\kasa\komuta\jev.json`; `YZ_JEV_AYAR` ortam değişkeni bu dosyanın yolunu değiştirir). Kullanılan alanlar: `credentials_file` (anahtar dosyasının mutlak yolu), `provider` (`vercel` ya da `typesafe`), `model`, `base_url`, `mode` (`off` ise uygulama da Jev'i hiç çağırmaz), isteğe bağlı `allow_custom_endpoint`. Anahtar **yalnızca** `credentials_file` dosyasından okunur (Vercel: `{"AI_GATEWAY_API_KEY": "…"}`, TypeSafe: `{"TYPESAFE_API_KEY": "…"}`); ortam değişkenleri okunmaz. Dosya yoksa ya da biçimi bozuksa Jev "hazır değil" sayılır ve uygulama kurallarla çalışır. Anahtar yalnızca bellekte ve istek başlığında kullanılır; hiçbir dosyaya, loga, duruma ya da hata metnine yazılmaz.

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
- **İstek belirteci**: her açılışta rastgele bir belirteç üretilir ve yalnızca bellekte tutulur. Arayüz adresi `http://127.0.0.1:PORT/#t=...` biçimindedir; `#` sonrası sunucuya gitmez, arayüz belirteci alıp oturum belleğine koyar ve adresten siler. Her `/api/*` isteği (GET dahil) `X-YZ-Token` başlığını taşımalı, yoksa ya da yanlışsa 403 döner. Masaüstü sürümü, ikinci kez açılışta çalışan örneğe pencere açabilmek için belirteci `%LOCALAPPDATA%\YZMerkezi\belirtec` dosyasına yazar (depoda değildir); port meşgulken önce `GET /api/kimlik` ile çalışan örneğin gerçekten bu uygulama olduğu doğrulanır, değilse hiçbir pencere açılmaz.
- **Güvenlik başlıkları**: tüm yanıtlarda `X-Frame-Options: DENY`, sıkı bir `Content-Security-Policy` (satır içi script/stil yok), `X-Content-Type-Options: nosniff`, `Referrer-Policy: no-referrer`, `Cross-Origin-Resource-Policy: same-origin`.
- **İstek sınırları**: gövde en çok 1 MB ve 10 sn'de okunur, JSON nesnesi olmalıdır. Beklenmeyen hatalarda arayüze yalnızca kısa bir kod gider; ayrıntı `%LOCALAPPDATA%\YZMerkezi\hata.log` dosyasına yazılır.
- **Allowlist'ler**: `/api/ayar` şemayla doğrulanır (bilinmeyen değerler reddedilir); masaüstü programı olarak yalnızca açık ve yerel sürücüdeki `.exe` dosyaları eklenebilir (ağ yolu, `.bat`, tarayıcılar reddedilir) ve her açılışta yol yeniden denetlenir; site adresleri yalnızca ilgili sitenin alan adına gidebilir. Çok hedefli ilk gönderimde "Şu hesaplara gidecek" onayı istenir (Ayarlar → Genel'den kapatılabilir).
- **Tarayıcı denetimi ağ portu olmadan**: Edge, `--remote-debugging-pipe` ile başlatılır; Chrome DevTools Protocol yalnızca uygulamanın kendisiyle Edge arasındaki iki anonim borudan (pipe) konuşulur. Hiçbir TCP portu dinlenmez (`netstat -ano` ile görülebilir); bu yüzden aynı bilgisayardaki başka bir program ya da bir web sayfası tarayıcıya bağlanıp oturum çerezlerini (`Network.getAllCookies`) okuyamaz. Boru yalnızca uygulamayı başlatan süreçte olduğundan, ikinci kez açılan `baslat.bat` bile tarayıcıya bağlanamaz; pencereyi çalışan uygulamaya belirteçli `POST /api/pencere-ac` isteğiyle açtırır. Uygulama kapanınca boru kapanır ve Edge de kapanır.
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

## Hafıza OS bağlantısı

Masaüstü sürümü, kişisel hafıza kasana (Hafıza OS, varsayılan `D:\YusufII\HAFIZAM1\kasa`; `YZ_KASA` ortam değişkeniyle değişir) bağlıdır; ChatGPT, Gemini ve Claude aynı hafızadan beslenir. Ayarlar → **Hafıza** bölümünde iki anahtar (ikisi de varsayılan açık), kasanın yolu ve durum görünür.

Veri akışı:
1. **Okuma ("Hafızayı mesaja ekle")**: mesaj gönderilirken kasadaki `araclar/hafiza.py --vault . context "<mesaj>" --limit 5 --char-budget 1200 --local` yerel bir alt süreç olarak çalıştırılır (kasa klasörü çalışma klasörüdür, en çok 10 sn; `--local` ile Mem0 ve ağ kullanılmaz). Dönen bağlam mesajın başına `Bağlam (kişisel notlarımdan, yalnızca gerekiyorsa kullan):` başlığıyla eklenir ve `---` çizgisinden sonra senin mesajın gelir. **Eklenen bağlam, mesajı alan her siteye (işaretli hesaplara) gider**; yani kasadan seçilen satırlar o şirketlerin sunucularına ulaşır. İstemediğinde anahtarı kapat.
2. **Sır süzgeci**: dönen metinde `sk-`, `AIza`, `ghp_`, `-----BEGIN`, parola, şifre (ve password, API key benzeri) geçen satırlar atılır; yani sır benzeri kayıtlar siteye gitmez. Bağlam boşsa, araç hata verirse ya da zaman aşımına uğrarsa hiçbir şey eklenmez ve mesaj olduğu gibi gider (sebep Ayarlar → Hafıza durumunda görünür).
3. **Geçmiş**: yerel sohbet geçmişinde ham mesaj ve eklenen bağlam ayrı alanlarda tutulur; mesaj balonunun altında katlanabilir "Hafızadan eklenen bağlam (N karakter)" bölümü neyin gittiğini gösterir. "Yeniden gönder" ham mesajı yeniden gönderir (bağlam yeniden aranır).
4. **Yazma ("Yanıtları hafızaya aday olarak yaz")**: Hafıza OS'a (katalog, Mem0, `hafiza.py candidate-add` kuyruğu) doğrudan yazılmaz; o kuyruk kaynak dosyada aynen bulunan doğrulanmış gerçekler içindir, sohbet yanıtı özetleri bu koşulu taşımaz. Bunun yerine kasanın ham giriş klasörüne `gelen-kutusu/yz-merkezi/YYYY-MM-DD.md` dosyasına **yalnızca ekleme** yapılır (frontmatter: `kaynak: yz-merkezi`; her kayıt: zaman, site, soru özeti en çok 200, yanıt özeti en çok 600 karakter). Var olan dosya ve notlar silinmez, taşınmaz, yeniden adlandırılmaz, üzerine yazılmaz; soru ya da yanıtında sır benzeri içerik olan kayıt hiç yazılmaz; aynı kayıt iki kez yazılmaz. Bu kayıtlar onaylı bilgi değildir, kasanın kendi inceleme akışı değerlendirir.
5. **Durum**: `GET /api/hafiza-durum` yanıtı `{kasa_var, hafiza_py_var, son_mod, son_hata}` (ve arayüzde gösterilen `kasa` yolu) döner.

Testler gerçek kasaya dokunmaz: `testler/_ortam.py` `YZ_KASA`'yı var olmayan geçici bir yola yönlendirir, `test_hafiza_kopru.py` geçici bir kasa ve sahte `araclar/hafiza.py` kurar.

## Klasör yapısı

- `masaustu_sunucu.py`: masaüstü sürümünün arka ucu (site durumu, sohbet listesi, gönderme, yanıt okuma, dizme; yedek olarak masaüstü programları)
- `arayuz-masaustu/`: masaüstü sürümünün Claude düzenindeki Türkçe arayüzü
- `pencereler.py`: Windows pencerelerini bulma, dizme ve yazı gönderme
- `tarayici.py`: Edge'i CDP borusuyla (ağ portu yok) ve ayrı profille (`%LOCALAPPDATA%\YZMerkezi\tarayici-profili`) başlatır; site sekmelerini bulur, pencere açar/dizer
- `cdp.py`: Edge'i Chrome DevTools Protocol ile anonim borular üzerinden denetleyen küçük istemci (`BoruBaglantisi`, sekme oturumu `Oturum`; yalnızca standart kütüphane)
- `siteler.py`: ChatGPT, Gemini ve Claude sitelerinin seçicileri ve sayfada çalışan JS parçaları (giriş denetimi, sohbet listesi, mesajlar, gönderme, yanıt)
- `hassas.py`: gönderme öncesi hassas bilgi taraması (API anahtarı, T.C. kimlik, IBAN/kart, parola; kural tabanlı)
- `yonlendirici.py` ve `yonlendirme.json`: mesajı sınıflandırıp site/model önerir; tercih sırası `yonlendirme.json` dosyasında düzenlenir
- `jev.py`: Jev (TypeSafe karar modeli) istemcisi; hassas bilgi uyarısı, yönlendirme ve yanıt puanlamada kullanılır, kurallar yedektir (yalnızca standart kütüphane)
- `uygulamalar.json`: tanınan masaüstü programları (ChatGPT, Gemini, Claude)
- `guvenlik.py`: iki sunucunun ortak güvenlik yardımcıları (başlıklar, istek belirteci, gövde sınırı, hata günlüğü, ayar dosyası yazma/yedekleme)
- `hafiza_kopru.py`: Hafıza OS köprüsü (kasadaki `hafiza.py context` çağrısı, sır süzgeci, gelen kutusuna aday kayıt ekleme; yalnızca standart kütüphane)
- `sunucu.py`: API sürümünün yerel sunucusu ve sağlayıcı bağdaştırıcıları (OpenAI uyumlu, Anthropic, Gemini)
- `saglayicilar.json`: hazır sağlayıcı listesi; yeni bir satır eklemek yeni sağlayıcı demek
- `araclar/simge_uret.py`: simgeyi (SVG -> PNG -> ICO) yeniden üretir; `kisayol-olustur.ps1`: Masaüstü kısayolunu oluşturur
- `arayuz/`: Türkçe arayüz (HTML, CSS, JavaScript)
- `testler/`: otomatik testler, `python -m unittest discover testler` ile çalışır. `test_entegrasyon.py` gerçek Edge'i geçici profille açıp `sahte-site.html` (ChatGPT'yi taklit eden yerel sayfa ve `sahte-site.js`/`.css` dosyaları, yalnızca `YZ_TEST=1` iken sunulur) üzerinde uçtan uca dener; Edge yoksa atlanır, gerçek sitelere hiç bağlanmaz. `testler/_ortam.py` testlerde ayar dosyası, profil ve veri klasörünü geçici yollara yönlendirir (gerçek dosyalara ve gerçek `%LOCALAPPDATA%\YZMerkezi` klasörüne dokunulmaz)
