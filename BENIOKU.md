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
- **Genel**: adın, Enter'a da bas, gönderince kutuyu temizle, yerleşim (bu pencere solda sütun mu altta çubuk mu).
- **Görünüm**: tema (Açık / Koyu / Sistem), yazı boyutu.
- **Programlar**: üstte "Hesaplar (web)" (durum ve "Pencereyi aç / Öne getir"), altta yedek masaüstü programları (Aç, Yazı kutusunu öğret, Kaldır; yeni program ekleme).
- **Kısayollar**: Enter gönder, Shift+Enter yeni satır, Ctrl+Shift+O yeni sohbet, Ctrl+B kenar çubuğu, Ctrl+, ayarlar, Ctrl+Shift+D yan yana diz.

Yedek yol (masaüstü programları): bilgisayarında kurulu ChatGPT, Gemini ve Claude programlarına pano ve tuş taklidiyle yazar. İlk açılışta seçili değildir; mesaj kutusundaki seçiciden işaretlersin.
- **Yazı kutusunu öğret**: bir programda mesaj yanlış yere gidiyorsa bu düğmeye bas, 4 saniye içinde fareyi o programın yazı kutusunun üstüne getir. Yer kaydedilir, pencere boyutu değişse de doğru çalışır.
- **Program ekle** (yazı kutusundaki + düğmesi): yeni bir yapay zeka programı kurduğunda ya da tarayıcıda bir sohbet sitesi açtığında onu aç, listeden seç.
- Gönderme sırasında fare ve klavye bir iki saniye programlar arasında gezer; o sırada fareye dokunma. Bir program öne getirilemezse ona hiçbir şey yazılmaz.
- Claude masaüstü uygulamasında hangi sohbet açıksa mesaj oraya gider.

Notlar:
- Site seçicileri (düğmeler, yazı kutusu, sohbet listesi) siteler güncellendikçe bozulabilir; hepsi `siteler.py` içinde tek yerdedir. Bir site yanıt vermezse sebep yazı kutusunun altındaki satırda görünür.
- Site pencerelerini kapatmak oturumu silmez; çerezler `%LOCALAPPDATA%\YZMerkezi\tarayici-profili` klasöründe kalır (proje klasöründe değil, GitHub'a gitmez). Uygulama çerezleri, belirteçleri ya da parolaları okumaz.
- Ayarlar ve yerel sohbet geçmişi `%LOCALAPPDATA%\YZMerkezi\masaustu-ayarlar.json` dosyasında durur. Arka uç `http://127.0.0.1:8766` adresinde yalnızca bu bilgisayardan erişilebilir.
- Veri konumu: varsayılan klasör `%LOCALAPPDATA%\YZMerkezi` (`YZ_VERI_KLASORU` ile değiştirilebilir); tek tek `YZ_MASAUSTU_AYAR`, `YZ_AYAR_DOSYASI`, `YZ_TARAYICI_PROFILI` ortam değişkenleri önceliklidir. Eski sürümlerden proje klasöründe kalan `masaustu-ayarlar.json`, `ayarlar.json` ve `.tarayici-profili` ilk açılışta bir kez bu klasöre taşınır (profil açık bir Edge tarafından kullanılıyorsa taşınmaz; Edge'i kapatıp yeniden aç).

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

## Klasör yapısı

- `masaustu_sunucu.py`: masaüstü sürümünün arka ucu (site durumu, sohbet listesi, gönderme, yanıt okuma, dizme; yedek olarak masaüstü programları)
- `arayuz-masaustu/`: masaüstü sürümünün Claude düzenindeki Türkçe arayüzü
- `pencereler.py`: Windows pencerelerini bulma, dizme ve yazı gönderme
- `tarayici.py`: Edge'i CDP borusuyla (ağ portu yok) ve ayrı profille (`%LOCALAPPDATA%\YZMerkezi\tarayici-profili`) başlatır; site sekmelerini bulur, pencere açar/dizer
- `cdp.py`: Edge'i Chrome DevTools Protocol ile anonim borular üzerinden denetleyen küçük istemci (`BoruBaglantisi`, sekme oturumu `Oturum`; yalnızca standart kütüphane)
- `siteler.py`: ChatGPT, Gemini ve Claude sitelerinin seçicileri ve sayfada çalışan JS parçaları (giriş denetimi, sohbet listesi, mesajlar, gönderme, yanıt)
- `uygulamalar.json`: tanınan masaüstü programları (ChatGPT, Gemini, Claude)
- `guvenlik.py`: iki sunucunun ortak güvenlik yardımcıları (başlıklar, istek belirteci, gövde sınırı, hata günlüğü, ayar dosyası yazma/yedekleme)
- `sunucu.py`: API sürümünün yerel sunucusu ve sağlayıcı bağdaştırıcıları (OpenAI uyumlu, Anthropic, Gemini)
- `saglayicilar.json`: hazır sağlayıcı listesi; yeni bir satır eklemek yeni sağlayıcı demek
- `arayuz/`: Türkçe arayüz (HTML, CSS, JavaScript)
- `testler/`: otomatik testler, `python -m unittest discover testler` ile çalışır. `test_entegrasyon.py` gerçek Edge'i geçici profille açıp `sahte-site.html` (ChatGPT'yi taklit eden yerel sayfa ve `sahte-site.js`/`.css` dosyaları, yalnızca `YZ_TEST=1` iken sunulur) üzerinde uçtan uca dener; Edge yoksa atlanır, gerçek sitelere hiç bağlanmaz. `testler/_ortam.py` testlerde ayar dosyası, profil ve veri klasörünü geçici yollara yönlendirir (gerçek dosyalara ve gerçek `%LOCALAPPDATA%\YZMerkezi` klasörüne dokunulmaz)
