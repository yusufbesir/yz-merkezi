# Yapay Zeka Merkezi

GPT, Gemini, Claude ve bilgisayarındaki yerel modelleri tek ekranda, yan yana kullanmanı sağlayan Türkçe uygulama. Bir mesaj yazarsın, işaretli bütün pencerelere aynı anda gider ve yanıtları karşılaştırırsın.

İki sürümü var:

1. **Masaüstü sürümü (`baslat.bat`)**: ChatGPT, Gemini ve Claude web sitelerini kendi tarayıcı profilinde açıp birleştirir (bilgisayarda kurulu masaüstü programları yedek yol). API anahtarı gerekmez, kendi hesapların ve aboneliklerin kullanılır.
2. **API sürümü (`baslat-api.bat`)**: tarayıcıda çalışır, API anahtarlarıyla bağlanır.

## Masaüstü sürümü

`baslat.bat` dosyasına çift tıkla; Claude masaüstü uygulamasıyla aynı düzende bir "Yapay Zeka Merkezi" penceresi açılır (Edge'in uygulama penceresinde çalışır, adres çubuğu yoktur).

**Önce web hesapları, masaüstü programları yedek.** ChatGPT, Gemini ve Claude web siteleri bu uygulamanın kendi Edge profilinde (`.tarayici-profili`) açılır ve arka planda denetlenir; fare ve klavye taklidi gerekmez. API anahtarı yoktur, kendi hesapların ve aboneliklerin kullanılır.

İlk kullanım:
1. Sol kenar çubuğunda "Hesaplar ve programlar" altındaki **ChatGPT**, **Gemini** ve **Claude**'a tıkla; her biri kendi penceresinde açılır.
2. Açılan pencerede bir kez giriş yap. Oturum o profilde kalır; kullandığın normal Edge profiline dokunulmaz. Durum "Giriş yapıldı" (yeşil), "Giriş gerekli" (turuncu) ya da "Kapalı" olarak görünür; giriş gerekiyorsa yazı kutusunun üstünde bir uyarı şeridi çıkar.
3. Mesajı yaz; işaretli hesapların hepsine aynı anda gider, yanıtlar mesajın altında canlı akar (yazıyor… imleciyle) ve yerel geçmişe kaydedilir.

Düzen:
- **Sol kenar çubuğu**: Yeni sohbet, sohbet arama (hem yerel hem site sohbetlerinde), hesap ve program listesi, **Son sohbetler** (önce "Yapay Zeka Merkezi" ortak sohbetleri, sonra her sitenin kendi sohbetleri; ↻ Yenile düğmesi), en altta adın ve Ayarlar.
- **Orta alan**: karşılama (günün saatine göre), gönderdiğin mesajlar ve her mesajın altında site başına yanıt bloğu. Bir site sohbetine tıklarsan sohbet o sitenin penceresinden okunur: senin mesajların sağda, asistanın yanıtları solda (site rengi ve adıyla). Bu sohbetteyken mesaj yalnızca o siteye, o sohbete gider (istersen başka hedef de işaretleyebilirsin).
- **Yazı kutusu**: altta yuvarlak kutu. Sağdaki seçiciden mesajın gideceği hesapları ve (yedek olarak) masaüstü programlarını işaretlersin; turuncu ok ya da Enter ile gönderirsin, Shift+Enter yeni satır. Yeni sohbette site pencereleri de yeni sohbet sayfasına gider.
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
- Site pencerelerini kapatmak oturumu silmez; çerezler `.tarayici-profili` klasöründe kalır (bu klasör GitHub'a gönderilmez). Uygulama çerezleri, belirteçleri ya da parolaları okumaz.
- Ayarlar ve yerel sohbet geçmişi `masaustu-ayarlar.json` dosyasında durur. Arka uç `http://127.0.0.1:8766` adresinde yalnızca bu bilgisayardan erişilebilir.

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

Anahtarlar yalnızca bu klasördeki `ayarlar.json` dosyasında saklanır, tarayıcıya ya da GitHub'a gönderilmez. İstersen `OPENAI_API_KEY`, `GEMINI_API_KEY`, `ANTHROPIC_API_KEY` ortam değişkenlerini de kullanabilirsin.

## Yeni çıkan modeller

- **Model listesi her seferinde sağlayıcıdan canlı çekilir.** Yeni bir model yayınlandığı gün listede, en üstte görünür; uygulamayı güncellemen gerekmez.
- Listede henüz yoksa model seçiminde **"✎ Model adını elle yaz…"** ile kimliğini yazabilirsin.
- Yeni bir şirket ya da servis çıkarsa **Ayarlar → Yeni sağlayıcı ekle** ile adresini gir. Çoğu servis "OpenAI uyumlu" çalışır.
- Hazır gelen ek sağlayıcılar: xAI (Grok), DeepSeek, Mistral, Groq ve tek anahtarla yüzlerce modele erişim veren OpenRouter.

## Bilgisayardaki (yerel) modeller

Ollama, LM Studio, Jan, llama.cpp, vLLM, GPT4All veya Text Generation WebUI çalışıyorsa uygulama açılışta onları kendiliğinden bulur. Sonradan açtıysan **Yerel modelleri tara** düğmesine bas. Yerel modeller internet ve anahtar gerektirmez.

Örnek: https://ollama.com adresinden Ollama'yı kur, `ollama pull llama3.2` komutunu çalıştır, sonra **Yerel modelleri tara**.

## Klasör yapısı

- `masaustu_sunucu.py`: masaüstü sürümünün arka ucu (site durumu, sohbet listesi, gönderme, yanıt okuma, dizme; yedek olarak masaüstü programları)
- `arayuz-masaustu/`: masaüstü sürümünün Claude düzenindeki Türkçe arayüzü
- `pencereler.py`: Windows pencerelerini bulma, dizme ve yazı gönderme
- `tarayici.py`: Edge'i uzaktan denetim portuyla (varsayılan 9230, `YZ_CDP_PORT`) ve ayrı profille (`.tarayici-profili`) başlatır
- `cdp.py`: Edge'i Chrome DevTools Protocol ile denetleyen küçük WebSocket istemcisi (yalnızca standart kütüphane)
- `siteler.py`: ChatGPT, Gemini ve Claude sitelerinin seçicileri ve sayfada çalışan JS parçaları (giriş denetimi, sohbet listesi, mesajlar, gönderme, yanıt)
- `uygulamalar.json`: tanınan masaüstü programları (ChatGPT, Gemini, Claude)
- `sunucu.py`: API sürümünün yerel sunucusu ve sağlayıcı bağdaştırıcıları (OpenAI uyumlu, Anthropic, Gemini)
- `saglayicilar.json`: hazır sağlayıcı listesi; yeni bir satır eklemek yeni sağlayıcı demek
- `arayuz/`: Türkçe arayüz (HTML, CSS, JavaScript)
- `testler/`: otomatik testler, `python -m unittest discover testler` ile çalışır. `test_entegrasyon.py` gerçek Edge'i geçici profille açıp `sahte-site.html` (ChatGPT'yi taklit eden yerel sayfa, yalnızca `YZ_TEST=1` iken sunulur) üzerinde uçtan uca dener; Edge yoksa atlanır, gerçek sitelere hiç bağlanmaz
