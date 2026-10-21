> Bu dosya Yusuf'a (yusufbesir) ait notlardandır (YZ Merkezi arşivi; AgentMom için referans). yazan: [Claude Sonnet 5.5, alt ajan, 2026-10-21]. Yapay zeka ajanları bu dosyayı Yusuf'un kuralları çerçevesinde inceleyip değiştirebilir; silme kararı yalnız Yusuf'undur ve silme yalnızca Geri Dönüşüm Kutusu'na taşıyarak yapılır. Kurallar: D:\YusufII\HAFIZAM1\kasa\ORTAK-AJAN-KURALLARI.md.

# Abacus AI taraması (AgentMom için)

Yöntem: yalnız abacus.ai resmi yardım sayfaları okundu (salt okunur). Hesap açılmadı, anahtar girilmedi, satın alma yapılmadı. Üçüncü taraf incelemeler (KDnuggets, eesel, thegtmdirectory) yalnız ipucu sayıldı; "doğrulanamadı" etiketi taşır. Bu arşiv, "GELISTIRME-NOTLARI.md" içindeki OpenCode fikirleriyle (goal döngüsü, maliyet takibi, izin modeli, zamanlanmış görev, bildirim, çoklu çalıştırma, SKILL.md içe alma) çakışmayacak biçimde yazıldı; çakışan yerler "bkz. OpenCode #n" ile işaretli.

## Özet

- Abacus AI, tek aboneliğe bağlı çok modelli bir ürün ailesidir: ChatLLM (sohbet), Abacus AI Agent (eski adı DeepAgent; otonom ajan), Abacus AI Desktop + `abacusai` CLI (kodlama ajanı; CodeLLM'in güncel karşılığı), RouteLLM API (OpenAI uyumlu yönlendirmeli uç nokta) ve Enterprise Platform (AI Workflows, bağlayıcılar, özel sohbet botları, Python SDK).
- AgentMom için en değerli üç yüzey: (1) RouteLLM, OpenAI/Anthropic/Responses biçimlerini tek anahtarla veren uç nokta, yani bir "sağlayıcı" kaydı; (2) `abacusai` CLI, adaptör adayı (print modu, MCP, izin modları, kendi anahtarını getir); (3) "abacus_tools" sunucu tarafı araç döngüsü fikri ve sınır/kota tasarımı.
- Önemli uyarı: Abacus bulut hizmetidir; yerel öncelikli AgentMom'da yalnız isteğe bağlı, açık yetkili, ücretli bir sağlayıcı olarak yer almalıdır. Varsayılan kapalı.
- Fiyat sayfası ve DeepAgent sayfası birbiriyle çelişiyor (Pro 20 dolar mı 10 dolar mı); karar öncesi yeniden doğrulanmalı.

## Abacus AI özellik haritası

| Özellik | Ne olduğu (resmi sayfadan) | Durum | Kaynak |
|---|---|---|---|
| ChatLLM / Teams | Tek abonelikle çok sağlayıcılı model erişimi, görsel/video üretimi, ajan ve kodlama aracı; aboneliğe 20.000 kredi dahil | Doğrulandı (fiyat tutarsız) | [1], [2] |
| Abacus AI Agent (eski DeepAgent) | Uçtan uca plan-yürüt ajanı: tam yığın web/mobil uygulama, GitHub PR akışı, sunum/rapor, gerçek tarayıcı/masaüstü kullanımı, paralel ajan sürüsü; Gmail, Slack, GitHub, Jira, veritabanı ve yüzlerce MCP bütünleştirmesi; zamanlama ve tetikleyiciler; çaba seviyeleri (xLow, Auto, High, xHigh, Max); görev başı yaklaşık 500-1.000 kredi, çoğu görev 5-25 dk | Doğrulandı. Bellek/sandbox/limit ayrıntısı sayfada yok: doğrulanamadı | [3] |
| Abacus AI Desktop + `abacusai` CLI | Kodlama ajanı; kurulum npm (`@abacus-ai/cli`, Node 18+) veya betik; `/login` ya da `ABACUS_API_KEY`; `--print/-p` ile etkileşimsiz çıktı, `--model`, `--permission-mode` (normal, accept-edits, plan, yolo), `--settings` dosyası (CI için), `--mcp-config` | Doğrulandı (CLI bayrakları arama özetinden; canlı `--help` ile teyit gerekir) | [4], [5], [6] |
| CodeLLM | Eski ad olarak anılıyor; güncel yardım ağacında Desktop/CLI olarak görünüyor. Üçüncü taraf kıyaslama iddiası (TerminalBench 62.3%) satıcı beyanı | CodeLLM adı resmi sayfada doğrulanamadı; benchmark doğrulanamadı | [7] |
| RouteLLM API | `route-llm` (otomatik model seçimi) veya adlı model; Chat Completions, Responses, Anthropic Messages, ayrıca `/v1/decisions`, `/v1/systemone`; akış, araç çağırma, çok kipli girdi, JSON şema, PDF girdisi, ses/görsel çıktı | Doğrulandı | [8], [9] |
| Bağlayıcılar | Kullanıcı bağlayıcıları (kişinin kendi hesabı, gerçek zamanlı) ve kurum bağlayıcıları (veritabanı, dosya, uygulama, mesajlaşma; izin duyarlı/RBAC seçeneği); Microsoft Entra onayı gerekebilir | Doğrulandı | [10] |
| MCP | Kullanıcı ve kurum düzeyinde MCP; CLI'de `~/.abacusai/mcp.json` ve `./.abacusai/mcp.json` (stdio ve uzak HTTP), `/mcp add/list/auth` | Doğrulandı (arama özetinden) | [10], [5] |
| Kendi anahtarını getir (BYOK) | CLI'de `useOwnApiKeys`, `/providers`; anahtarlar işletim sistemi güvenli deposunda; yerel/üçüncü taraf sağlayıcı eklenebilir | Doğrulandı | [6] |
| AI Workflows / ajanlar | Düğüm tabanlı iş akışı (veri dönüşümü, ML, LLM istemi); türler DEFAULT, CHAT, AUTONOMOUS; çevrimdışı veya çevrimiçi (API) dağıtım; konuşmalı ajan akış uç noktası | Doğrulandı. Değerlendirme, bellek, RAG, fiyat sayfada yok | [11] |
| Özel sohbet botları / RAG | Kurum bağlayıcılarından belge setleri ve MCP bağlı özel sohbet botu anılıyor; RAG ayrıntısı bulunan sayfalarda yok | Ayrıntı doğrulanamadı | [10], [12] |
| Bellek (kalıcı kullanıcı belleği) | İncelenen resmi sayfalarda belge bulunamadı | Doğrulanamadı | - |
| Python SDK | `ApiClient`, `get_api_endpoint().predict_endpoint`, OpenAI istemcisiyle LLM çağrısı, GitHub CI/CD bölümü | Doğrulandı (SDK kurulum adımı sayfada yok) | [13] |
| Fiyatlandırma | Basic 10 dolar/ay (ilk ay 7), 20.000 kredi, 3 ajan görüşmesi; Pro 20 dolar/ay, 30.000 kredi, sınırsız ajan/kodlama CLI. DeepAgent sayfası Pro için 10 dolar der: tutarsız. Teams/Enterprise/RouteLLM API fiyat sayfası yok | Kısmen doğrulandı | [14], [3] |

## API ve entegrasyon yüzeyi

- Kimlik doğrulama: `Authorization: Bearer <api_key>`. Anahtar Abacus RouteLLM API sayfasından alınır. Kurumsal çalışma alanında anahtar yalnız kendi alan adında geçerlidir; sabit `routellm.abacus.ai` adresi kurumsal anahtarı 403 ile reddeder [13].
- Taban adresler: bireysel `https://routellm.abacus.ai/v1`; kurumsal `https://<workspace>.abacus.ai/v1` [8]. Adres yapılandırılabilir olmalı.
- OpenAI uyumluluğu: Evet. `/v1/chat/completions`, `/v1/responses`, `/v1/messages` (Anthropic biçimi), `/v1/models` (güncel katalog ve fiyat) [8], [9]. Böylece AgentMom'un mevcut OpenAI uyumlu sağlayıcı türü doğrudan kullanılabilir; ek olarak Anthropic biçiminde de konuşulabilir.
- Parametreler: `model` (varsayılan `route-llm`), `messages`, `max_tokens`, `temperature` (0-2), `top_p`, `stream`, `stop` (en çok 4), `response_format` (`json_object`/`json_schema`), `tools`, `tool_choice`, eklenti alanları `abacus_tools`, `modalities`, `audio`, mesajda `file` (PDF) [9]. Düşünme kipi için model adına `-thinking` eki anılıyor (ikincil özet, doğrulanamadı).
- Sunucu tarafı araçlar (`abacus_tools`): kurumda kayıtlı araçlar adıyla çağrılır, sunucu döngüyü çalıştırır, yalnız son yanıt döner. Sınırlar: istek başı 20 araç, 8 model turu, araç çağrısı başı 300 sn, 200.000 karakter sonuç, kullanıcı başı saatte 1.000 çağrı; bağlayıcı araçları hariç; hangi aracın çalıştığı yanıtta görünmez; yeniden denemede yan etkili araç tekrar çalışabilir [9]. Güvenlik açısından AgentMom politikasına aykırı bir karanlık kutu: kullanılmamalı (bkz. Yapılmaması önerilenler).
- Hata biçimi: `{"error":{"message","type","code"}}`; 400, 401, 429, 500. Genel hız sınırı sayısal olarak belgelenmemiş; `max_tokens` ve yeniden deneme önerilir [8], [9].
- Kullanım bilgisi: `usage` içinde `prompt_tokens`, `completion_tokens`, `total_tokens`; akışta yalnız son parçada gelir [9].
- Ücretlendirme: Tescilli modeller sağlayıcı liste fiyatından, açık ağırlıklı modeller piyasa fiyatına yakın (ABD'de barındırılır); abonelik kredisi ile tüketilir, kredi bitince abonelere kullanım sürer [8]. Kredi/dolar eşlemesi ve RouteLLM'in faturalama ayrıntısı sayfada yok: doğrulanamadı.
- SDK: Python `abacusai` SDK + `openai` istemcisi; TypeScript için `body` ile `abacus_tools` geçirilir. AgentMom'un TypeScript/Node ağırlıklı olacağı varsayımıyla ayrı SDK gerekmez; düz HTTP yeterli.
- CLI: `abacusai` (npm `@abacus-ai/cli`); `ABACUS_API_KEY`; MCP yapılandırma dosyaları; yerel/üçüncü taraf sağlayıcı ekleme; izin kipleri [4]-[6]. Sözleşme ayrıntıları (çıktı biçimi, çıkış kodları, JSON akışı) belgelenmedi: adaptör yazmadan önce kurulum onayıyla yerinde keşif şart.

## AgentMom'a entegrasyon önerileri

Öncelik sırasına göre. Boyut: S küçük, M orta, L büyük.

1. RouteLLM'i "OpenAI uyumlu sağlayıcı" olarak kayıt defterine ekle
   - Ne: Sağlayıcı kaydı (`abacus-routellm`): taban adres (bireysel/kurumsal ayarlı), model listesi `/v1/models` ile dinamik, `route-llm` otomatik model seçimi seçeneği.
   - Neden: Tek anahtarla 20'den fazla modele erişim; AgentMom'un sağlayıcıdan bağımsız hedefine uyar; mevcut OpenAI uyumlu sağlayıcı koduyla neredeyse sıfır ek kod.
   - Nasıl: Sağlayıcı kayıt defterinde yeni giriş + sır kasasında anahtar; model kipinde seçilebilir; ücretli olduğu için politika motorunda "ücretli API" etiketi ve açık yetki (oturum başı onay, günlük bütçe).
   - Bağımlılık: Abacus API anahtarı ve abonelik/kredi (ücretli).
   - Risk: Veri bulut tarafına gider (yerel öncelik ilkesiyle çelişir); fiyat ve model adı değişkenliği; hız sınırı belgesiz.
   - Boyut: S.

2. Yönlendirme şeffaflığı: "route-llm" seçildiğinde gerçekten hangi model çalıştı?
   - Ne: Yanıt üstverisinden (varsa `model` alanı) çalışan modeli kaydet; yoksa kullanıcıya "otomatik seçildi, model bilinmiyor" göster.
   - Neden: Maliyet ve denetim izi için; Abacus yönlendirici kararı doğrulanamıyor.
   - Nasıl: Sağlayıcı katmanında yanıt normalleştirici; günlük kaydı. OpenCode #2 (kullanım/maliyet takibi) ile birleştirilebilir.
   - Bağımlılık: Yok (#1 sonrası).
   - Risk: Yanıtta model alanı dönmeyebilir (doğrulanamadı).
   - Boyut: S.

3. `abacusai` CLI'yi ajan adaptörü olarak ekle (deneysel)
   - Ne: Claude Code/Codex/Gemini CLI/OpenCode yanına beşinci adaptör: `abacusai -p "<görev>" --model <id> --permission-mode plan` ile salt-okur/plan kipinde çalıştırma.
   - Neden: Abacus, aboneliğe dahil kodlama ajanı sunuyor; CLI kendi anahtarını (BYOK) ve MCP'yi destekler; AgentMom'un ajan kayıt defterine doğal uyar.
   - Nasıl: Ajan kayıt defteri girişi (`abacusai`, sürüm algılama `--help`), adaptör `--print` ile çıktı toplar, izin kipi AgentMom politikasından türetilir (varsayılan plan/normal; `yolo` yasak). Çıktı biçimi belgesiz olduğu için önce yerinde keşif.
   - Bağımlılık: CLI kurulumu (Yusuf onayı gerekir; kurulum betiği uzaktan çalıştırılır, bu yüzden npm yolu tercih), Abacus hesabı/anahtar (ücretli).
   - Risk: Kapalı kaynak, bulut bağımlı; çıktı sözleşmesi belirsiz; `--permission-mode` değerleri sürümle değişebilir.
   - Boyut: M.

4. MCP yapılandırmasını Abacus CLI ile paylaşma (tek kaynaklı MCP kaydı)
   - Ne: AgentMom'un MCP kayıt defterinden `.abacusai/mcp.json` üretme/çalıştırmada `--mcp-config <dosya>` verme.
   - Neden: Her ajana aynı MCP sunucularını, aynı izinlerle sunmak; elle çoğaltma hatası olmaz.
   - Nasıl: Adaptör çalıştırma öncesi geçici yapılandırma dosyası yazar, bitince geri dönüşüm kutusuna taşır (silme kuralı); sırlar dosyaya değil ortam değişkenine.
   - Bağımlılık: #3.
   - Risk: Sır sızıntısı (dosyada); yapılandırma biçimi değişikliği.
   - Boyut: S-M.

5. Kullanıcı/kurum bağlayıcı ayrımını AgentMom izin modeline taşıma
   - Ne: Abacus'un "kullanıcı bağlayıcısı (kişinin kimliğiyle, gerçek zamanlı) / kurum bağlayıcısı (paylaşımlı hizmet hesabı)" ayrımı ve "izin duyarlı (RBAC) bağlayıcı" kavramı.
   - Neden: AgentMom politika motoru için hazır, anlaşılır bir sınıflandırma: her MCP/araç kaydına "kimlik türü" alanı eklemek.
   - Nasıl: Politika şemasına `kimlik: kullanici | paylasimli` alanı; paylaşımlı kimlikli araçlar için varsayılan "sor". OpenCode #6 izin modeliyle birlikte tasarlanmalı.
   - Bağımlılık: Yok (tasarım fikri).
   - Risk: Aşırı şemalaştırma.
   - Boyut: S.

6. Çaba seviyesi kavramı (xLow-Auto-High-xHigh-Max) -> AgentMom "çaba/bütçe" ayarı
   - Ne: Her görev için çaba seviyesi; düşük çaba yerel/ucuz model, yüksek çaba pahalı model.
   - Neden: Abacus ajanında maliyet-kalite takası kullanıcıya tek düğmeyle sunuluyor; AgentMom'da "ücretli API için açık yetki" ile doğal eşleşir.
   - Nasıl: Politika motoru çaba seviyesini model/sağlayıcı sıralamasına eşler; tahmini kredi/jeton ön gösterimi (OpenCode #2/#3 ile birleştir).
   - Bağımlılık: Birden çok sağlayıcı (en az bir yerel).
   - Risk: Eşleme tablosunun bakımı.
   - Boyut: M.

7. Sağlayıcı sağlık/hata sınıflandırması (429/401/403 kurumsal-bireysel adres uyuşmazlığı)
   - Ne: Hata kodlarına göre davranış: 401 anahtar geçersiz uyarısı, 403 "yanlış çalışma alanı adresi" ipucu, 429 geri çekilme + yedek sağlayıcıya geçiş önerisi.
   - Neden: Abacus belgesinde kurumsal anahtarın bireysel adreste 403 verdiği açıkça uyarılıyor [13]; hazır bir hata ipucu.
   - Nasıl: Sağlayıcı adaptöründe hata eşleyici + yedek zinciri (kullanıcı onaylı).
   - Bağımlılık: #1.
   - Risk: Yok denecek kadar az.
   - Boyut: S.

8. PDF/dosya girdisi ve JSON şema çıktısını model kipi yeteneği olarak işaretleme
   - Ne: Sağlayıcı yetenek bayrakları: `json_schema`, `pdf_input`, `image_input`, `audio_output`, `streaming`, `tool_calls`.
   - Neden: RouteLLM bu özellikleri tek uç noktada sunuyor; AgentMom yetenek tabanlı model seçimi (örn. "yapılandırılmış çıktı gerekiyorsa yalnız şema destekli sağlayıcılar") yapabilir.
   - Nasıl: Model kayıt defterine yetenek alanı; `/v1/models` yanıtı yetenek bildirmezse elle tablo.
   - Bağımlılık: #1.
   - Risk: Yetenekler modele göre değişir, doğrulama testi gerekir.
   - Boyut: M.

9. Zamanlanmış/tetikli görev ve "kendini geliştiren görev" fikri (yalnız fikir; OpenCode #7 ile birleşik)
   - Ne: Abacus ajanındaki zamanlama + tetikleyici + sonuçtan öğrenme. AgentMom'da zamanlanmış görev bitince sonuç özeti ve "bir sonraki çalışmaya notlar" yerel dosyaya yazılsın.
   - Neden: Tekrarlayan işler için; ancak otomatik kendini değiştirme olmasın, yalnız not önerisi.
   - Nasıl: Zamanlayıcı modülü + yerel not deposu; yetki politikası aynen uygulanır.
   - Bağımlılık: Yok (yerel).
   - Risk: Yetkisiz özerklik; yalnız not önerisiyle sınırlandır.
   - Boyut: M.

10. Kendi anahtarını getir (BYOK) sır deseni
   - Ne: Abacus CLI'nin yaptığı gibi anahtarı işletim sistemi güvenli deposuna yazma ve ayar dosyalarına hiç yazmama; ortam değişkeni ile geçici geçirme.
   - Neden: AgentMom sır kasası zaten planlı; bu, doğrulanmış bir referans desen.
   - Nasıl: Windows Kimlik Bilgisi Yöneticisi veya DPAPI; adaptör alt sürece yalnız gerekli değişkeni verir; günlükte maskeleme.
   - Bağımlılık: Yok.
   - Risk: Alt süreç ortamının sızması; günlük maskeleme testi.
   - Boyut: S-M.

11. Karşılaştırmalı çalıştırma: aynı istemi `route-llm` ve yerel modelle çalıştırıp kalite/maliyet kıyası (opsiyonel)
   - Ne: İstem tek, iki sağlayıcı; sonuçlar yan yana. OpenCode #10 (çoklu çalıştırma) ile aynı arayüz.
   - Neden: "Yönlendirici gerçekten fayda sağlıyor mu?" sorusunu ölçmek.
   - Nasıl: Model kipine çoklu çalıştırma düğmesi; ücretli çağrı için onay.
   - Bağımlılık: #1, yerel model.
   - Risk: Çifte maliyet.
   - Boyut: M.

## Yapılmaması önerilenler

- `abacus_tools` (sunucu tarafı araç döngüsü) kullanma: hangi aracın çalıştığı görünmez, yeniden denemede yan etkili araç tekrarlanabilir; AgentMom'un politika/denetim ilkesine aykırı. Araçlar yerelde çalışsın.
- Abacus Agent (DeepAgent) uzak ajanını AgentMom ajanı olarak sürme: gerçek tarayıcı/masaüstü kontrolü, 5-25 dk bulut görevleri, kredi tüketimi ve veri çıkışı yerel öncelik ilkesiyle uyumsuz; yalnız kullanıcı kendisi kullansın.
- `yolo` izin kipi ve `--permission-mode` ile tam yetki verme.
- Kurulum betiğini `curl | bash` / `irm | iex` ile çalıştırma; gerekirse npm paketi ve sürüm sabitleme, Yusuf onayıyla.
- Abacus bağlayıcıları (Gmail, Slack, Jira vb.) üzerinden e-posta/mesaj gönderme yetkisi verme; AgentMom'da gönderim her zaman açık onaylı.
- Fiyat/kredi varsayımlarını koda gömme; fiyat tutarsız ve değişken.
- Üçüncü taraf benchmark iddialarına (TerminalBench vb.) göre ajan seçme.
- Abacus'u zorunlu bağımlılık yapma; hiçbir çekirdek özellik Abacus olmadan çalışmaz hale gelmesin.

## Yusuf'un kararını bekleyen sorular

1. Abacus aboneliği (Basic 10 / Pro 20 dolar) alınsın mı, yoksa yalnız belge düzeyinde mi kalınsın? (Satın alma yapılmadı.)
2. `abacusai` CLI kurulumu (npm) denemesi için onay veriyor musun? Kurulumsuz adaptör yazılamaz.
3. Veri bulut tarafına gideceği için Abacus yalnız "genel/gizli olmayan" görevlerde mi kullanılsın; hassas tarama (sır/PII) filtresi zorunlu olsun mu?
4. Günlük/aylık ücretli API bütçe üst sınırı ne olsun?
5. Öncelik: sağlayıcı kaydı (#1) mı, CLI adaptörü (#3) mı, ikisi birden mi?

## Kaynaklar

[1] https://chatllm.abacus.ai/ (ChatLLM Teams)
[2] https://www.kdnuggets.com/2026/06/abacus/abacus-ai-chatllm-review (ikincil, doğrulanamadı bölümleri işaretli)
[3] https://abacus.ai/help/chatllm-ai-super-assistant/deepagent
[4] https://abacus.ai/help/abacusai-desktop/cli-installation
[5] https://abacus.ai/help/abacusai-desktop/mcp-configuration
[6] https://abacus.ai/help/abacusai-desktop/providers
[7] https://abacus.ai/help/abacusai-desktop/introduction
[8] https://abacus.ai/help/route-llm/
[9] https://abacus.ai/help/route-llm/chat-completions/
[10] https://abacus.ai/help/connectors/introduction ve https://abacus.ai/help/connectors/mcpServers
[11] https://abacus.ai/help/developer-platform/useCases/AI_AGENTS
[12] https://abacus.ai/help/developer-platform/introduction
[13] https://abacus.ai/help/python-sdk/genai/calling-llms
[14] https://abacus.ai/pricing

## Kullanılan araçlar ve tahmini token

- Araçlar: Read, Grep, ToolSearch, WebSearch (3 arama), WebFetch (11 sayfa), Write (bu dosya). Hesap, kurulum, satın alma, anahtar işlemi yok; kasaya ve anahtarlar klasörüne dokunulmadı.
- Tahmini token: yaklaşık 60-70 bin toplam (giriş ağırlıklı; çıktı yaklaşık 6-7 bin).
- Not: CLI bayrakları ve MCP yolları arama özetinden alındı; sayfaların kendisi doğrudan okunarak teyit edilmedi.
