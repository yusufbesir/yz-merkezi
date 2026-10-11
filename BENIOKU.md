# Yapay Zeka Merkezi

GPT, Gemini, Claude ve bilgisayarındaki yerel modelleri tek ekranda, yan yana kullanmanı sağlayan Türkçe uygulama. Bir mesaj yazarsın, işaretli bütün pencerelere aynı anda gider ve yanıtları karşılaştırırsın.

İki sürümü var:

1. **Masaüstü sürümü (`baslat.bat`)**: bilgisayarında kurulu ChatGPT, Gemini ve Claude programlarını birleştirir. API anahtarı gerekmez, kendi hesapların ve aboneliklerin kullanılır.
2. **API sürümü (`baslat-api.bat`)**: tarayıcıda çalışır, API anahtarlarıyla bağlanır.

## Masaüstü sürümü

`baslat.bat` dosyasına çift tıkla; ekranda küçük bir "Yapay Zeka Merkezi" çubuğu açılır.

- **Hepsini aç**: kapalı olan programları açar ve ekranda yan yana dizer.
- **Yan yana diz**: açık programları ekranı eşit bölerek yan yana koyar, kontrol çubuğunu en alta alır.
- **Gönder** (ya da Enter): yazdığın mesajı işaretli programların hepsine yapıştırır ve gönderir. Shift+Enter yeni satır açar. "Enter'a da bas" işaretini kaldırırsan sadece yapıştırır, göndermeyi sen yaparsın.
- **Yazı kutusunu öğret**: bir programda mesaj yanlış yere gidiyorsa bu düğmeye bas, 4 saniye içinde fareyi o programın yazı kutusunun üstüne getir. Yer kaydedilir, pencere boyutu değişse de doğru çalışır.
- **Program ekle**: yeni bir yapay zeka programı kurduğunda (ya da tarayıcıda bir sohbet sitesi açtığında) onu aç, bu düğmeyle listeden seç. Artık o da mesaj alır.

Notlar:
- Gönderme sırasında fare ve klavye bir iki saniye programlar arasında gezer; o sırada fareye dokunma.
- Bir program öne getirilemezse ona hiçbir şey yazılmaz, durum satırında sebebi görünür.
- Claude masaüstü uygulamasında hangi sohbet açıksa mesaj oraya gider.
- Ayarlar `masaustu-ayarlar.json` dosyasında durur.

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

- `masaustu.pyw`: masaüstü sürümünün kontrol çubuğu
- `pencereler.py`: Windows pencerelerini bulma, dizme ve yazı gönderme
- `uygulamalar.json`: tanınan masaüstü programları (ChatGPT, Gemini, Claude)
- `sunucu.py`: API sürümünün yerel sunucusu ve sağlayıcı bağdaştırıcıları (OpenAI uyumlu, Anthropic, Gemini)
- `saglayicilar.json`: hazır sağlayıcı listesi; yeni bir satır eklemek yeni sağlayıcı demek
- `arayuz/`: Türkçe arayüz (HTML, CSS, JavaScript)
- `testler/`: otomatik testler, `python -m unittest discover testler` ile çalışır
