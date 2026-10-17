> Bu dosya Yusuf'a (yusufbesir) ait Yapay Zeka Merkezi projesinin parçasıdır. yazan: [Claude Sonnet 5.5, alt ajan, 2026-10-17]. Yapay zeka ajanları bu dosyayı Yusuf'un kuralları çerçevesinde inceleyip değiştirebilir; silme kararı yalnız Yusuf'undur ve silme yalnızca Geri Dönüşüm Kutusu'na taşıyarak yapılır. Kurallar: BENIOKU.md ve D:\YusufII\HAFIZAM1\kasa\ORTAK-AJAN-KURALLARI.md.

# OpenCode ve OpenChamber araştırması (2026-10-17)

## Özet

- **OpenCode** (depo şimdi `github.com/anomalyco/opencode`, eski adres `sst/opencode`; MIT; ~215 bin yıldız) açık kaynak bir kodlama ajanıdır. Mimari sunucu/istemci: `opencode` çalışınca bir HTTP sunucusu başlar, terminal arayüzü onun istemcisidir. `opencode serve` yalnız sunucuyu çalıştırır (OpenAPI 3.1, SSE olay akışı, temel kimlik doğrulama). `opencode run --format json` tek seferlik başsız kullanım sağlar. JS/TS SDK (`@opencode-ai/sdk`) var; resmi belgede Python SDK yok.
- **OpenChamber** (`github.com/openchamber/openchamber`, MIT, ~11,7 bin yıldız, bağımsız proje, OpenCode ekibiyle bağlantısı yok) OpenCode üstüne kurulu masaüstü/web/PWA/VS Code/iOS/Android arayüzüdür. Yusuf'un listesindeki özelliklerin çoğu (Goal, Mini Chat, zamanlanmış görevler, proje notları/To-Do/planlar, tarayıcı, Cloudflare/ngrok, Android APK, önbellek sıcak tutma, otomatik yönlendirme, "güvenlik ağı" izin kipi) OpenChamber'ın Eylül-Ekim 2026 sürüm notlarında doğrulandı (en yeni sürüm v2.4.0, 17 Ekim 2026).
- Listede 33 satır incelendi: **28 Doğrulandı, 3 Kısmen, 2 Doğrulanamadı**. Doğrulanamayanlar: Abacus AI (resmi sağlayıcı listesinde yok; yalnız özel OpenAI uyumlu sağlayıcı olarak denenebilir) ve "~1 GB RAM" (hiçbir resmi kaynakta yok).
- **Öneri:** Önce fikirleri kendi kodumuza taşımak (seçenek a: Goal döngüsü, kullanım/maliyet, önbellek farkındalıklı yönlendirme, proje notları); sonra isteğe bağlı olarak OpenCode'u `opencode run --format json` ile dördüncü motor yapmak (seçenek b, tüm araçlar kapalı yapılandırmayla). OpenCode sunucusunu arka uç yapmak (seçenek c) güvenlik katmanlarımızı (hassas tarama, açılış kodu/çerez, Jev'e hassas veri gitmemesi) atlatan ikinci bir yetkili süreç doğurduğu için önerilmez.
- Uyarı: OpenCode'un sağlayıcı belgesi, Claude Pro/Max aboneliğinin üçüncü taraf eklentilerle OpenCode'da kullanılmasının Anthropic tarafından açıkça yasaklandığını söylüyor. Bizim yaklaşım (resmi `claude` CLI'yi çalıştırmak) farklıdır; OpenCode içinden Claude aboneliğiyle giriş yapılmamalı.

## Yusuf'un listesinin doğrulaması

| Özellik | Durum | Kaynak | Not |
|---|---|---|---|
| Çoklu sağlayıcı/model (genel) | Doğrulandı | opencode.ai/docs/providers | `/connect`, `opencode.json` `provider`, models.dev kataloğu, `provider/model` biçimi |
| xAI Grok | Doğrulandı | docs/providers | SuperGrok aboneliği (cihaz kodu OAuth) veya API anahtarı |
| Kimi (Moonshot) | Doğrulandı | docs/providers; docs/zen | `/models` içinde Kimi K2; Zen kataloğunda da var |
| Abacus AI | Doğrulanamadı | docs/providers (listede yok); 3. taraf kılavuz | Resmi destek yok. Abacus RouteLLM OpenAI uyumlu uç olarak anılıyor, `@ai-sdk/openai-compatible` ile elle eklenebilir; adres ve model kimlikleri doğrulanmadı |
| OpenCode Zen | Doğrulandı | docs/zen | Model geçidi (OpenCode Console), kullandıkça öde, maliyetine satış (kart işlem ücreti dahil), ABD/AB barındırma, çoğunda sıfır saklama; bazı ücretsiz dönem modelleri veriyi iyileştirmede kullanabilir |
| Abonelikle giriş (ChatGPT, Copilot, SuperGrok) | Doğrulandı | docs/providers | Claude Pro/Max girişi de listeli ama belge "üçüncü taraf eklentiler Anthropic tarafından yasak" diyor |
| Kota/token/önbellek maliyeti takibi | Kısmen | docs/cli (`opencode stats`); OpenChamber changelog | OpenCode: `stats --days --models --project`; OpenChamber: girdi/çıktı/önbellek ayrımı, bakiye kartları (ZenMux, Kilo, DeepInfra, NanoGPT, OpenCode Go), bağlam halkasında oturum maliyeti. xAI ve Kimi için ayrı kota kartı doğrulanmadı |
| Windows | Doğrulandı | github anomalyco/opencode; openchamber README | OpenCode: betik/npm/Scoop/Choco, belge "WSL önerilir" der; OpenChamber masaüstü Windows var ve OpenCode CLI'yi içinde getirir |
| macOS | Doğrulandı | aynı | Apple Silicon ve Intel |
| Android (APK) | Doğrulandı | openchamber releases v2.4.0 | APK 38,5 MB ve AAB 27 MB, 17 Ekim 2026; iOS uygulaması da var |
| Uzak örnekler (OpenChamber) | Doğrulandı | openchamber README | CLI/sunucu, Private Relay (QR, uçtan uca şifreli), doğrudan, LAN/VPN, SSH |
| Cloudflare / ngrok tüneli | Doğrulandı | openchamber README; changelog | README Cloudflare quick tunnel ve ngrok der; `openchamber tunnel start` tünel için arayüz parolası verir; "Enterprise mode" dış tünelleri kapatır |
| Ajan masaüstü bildirimleri | Doğrulandı | changelog v2.0.1, v2.1.1, v2.3.3 | Eklentiler/ajanlar bildirim yollayabilir; masaüstü izin bildiriminde istenen komut görünür; telefon push uçtan uca şifreli. OpenCode tarafı: `session.idle`, `permission.asked` olayları |
| Otomatik izin kuralları | Doğrulandı | docs/permissions; changelog v2.0.3 | OpenCode: allow/ask/deny, desen eşleme, son eşleşen kazanır, ajan başına geçersiz kılma, `--auto`. OpenChamber: oturum başına "sor / güvenlik ağı / hepsini kabul" kalkanı |
| Sınıflandırma (neyin sormadan çalışacağına model karar verir) | Kısmen | changelog v2.0.3 | "Güvenlik ağı" kipinde bir değerlendirici karar veriyor; kaynakta adı "Jev" geçiyor, Yusuf'un Jev'i ile ilişkisi doğrulanmadı (ad çakışması olabilir) |
| Modeller arası auto-routing | Doğrulandı | changelog v2.2.0, v2.3.1 | Ayarlar → Routing; önbellek sıcakken son modelde kalma; resimli mesajda uygun modeli seçme. OpenCode çekirdeğinde değil, OpenChamber katmanında |
| MCP | Doğrulandı | docs/mcp-servers | local (komut) ve remote (url), OAuth otomatik, `opencode mcp auth/list/logout/debug`, ajan başına açma/kapama |
| Context7 | Doğrulandı | docs/mcp-servers | Belgede örnek olarak var |
| Web arama | Doğrulandı | docs/tools | `websearch` (Exa/Parallel; OpenCode/Go sağlayıcısında ya da `OPENCODE_ENABLE_EXA=1`), anahtar gerekmez; `webfetch` ayrı |
| GitHub | Doğrulandı | docs/cli (`opencode github`); README | Actions iş akışı kurulumu; OpenChamber: sorun/PR'dan oturum başlatma, başarısız kontrolü ajana gönderme |
| Skill kütüphaneleri | Doğrulandı | docs/skills | `.opencode/skills`, `.claude/skills` ve `.agents/skills` okunur (Claude uyumlu); `permission.skill` ile kontrol |
| Obra's Superpowers | Doğrulandı | mintlify.com/obra/superpowers/installation/opencode (3. taraf) | `plugin` dizisine git adresi; Windows'ta git adresli eklenti kurulumunda sorun bildirilmiş (npm ile kurma önerilmiş) |
| Goal modu | Doğrulandı | openchamber README; changelog v2.0.4, v2.1.1 | Her tur sonrası değerlendirici "bitti / sürüyor / seni bekliyor" der; otomatik tur sınırı 1-200 ayarı. OpenCode çekirdeğinde yok |
| Dahili terminal | Doğrulandı | changelog v2.1.0, v2.3.0 | Sekmeler, yeniden adlandırma, sohbetin yanına taşıma |
| Git commit/PR, değişiklik geçmişi | Doğrulandı | changelog v2.1.1-v2.3.0; docs (`/undo`, `snapshot`) | Depo başına kimlik, pull(rebase), PR/MR oluşturma-birleştirme; OpenCode `snapshot` (varsayılan açık) ile geri alma; "Changes Walkthrough" diff anlatımı |
| Proje To-Do, notlar, plan dosyaları | Doğrulandı | changelog v2.2.0, v2.3.2, v2.4.0 | "Project knowledge" paneli; ajan kendi aracıyla okur/değiştirir; notlar sıkıştırma ve fork'tan sağ çıkar |
| Dahili tarayıcı | Doğrulandı | README "Preview"; changelog v2.3.0 | Oturum başına sekme, eleman seçip ajana gönderme |
| Mini sohbet pencereleri | Doğrulandı | changelog v2.2.0, v2.3.2 | Küresel kısayol, üstte sabit pencere |
| Oturum sıcak tutma (keep-alive) | Kısmen | changelog v2.0.1, v2.2.0 | Ayarlar → Sessions anahtarı boştaki oturumun önbelleğini küçük arka plan istekleriyle sıcak tutar. Sağlayıcı önbellek süresi ve maliyet etkisi kaynakta anlatılmıyor |
| Zamanlanmış görevler | Doğrulandı | README; changelog v2.1.0, v2.2.0 | Bir kez, günlük, haftalık, cron; Goal ile birlikte; depodaki "loop" dosyaları yalnız yerelde açılınca çalışır |
| Çoklu çalıştırma / birleştirme | Doğrulandı | README | Aynı görev en çok 5 modelde, ayrı worktree; "Fusion" en iyi kısımları birleştirir |
| Masaüstü sürümünde OpenCode CLI gömülü | Doğrulandı | openchamber README | Web/VS Code için ayrı kurulum gerekir (Node 24.14+) |
| ~1 GB RAM | Doğrulanamadı | hiçbir resmi sayfa | OpenCode sunucusu ve OpenChamber için bellek kullanımı yayımlanmamış; ölçüm gerekir (kurulum yapılmadı) |

Sınırlama: OpenChamber changelog sayfasının 384 bin karakterinden yalnız ilk 100 bini okundu; eski sürümlerdeki özellikler kaçmış olabilir. Okunan sayfalar küçük bir model tarafından özetlendi; kritik sayılar (sürüm, tarih, boyut) kullanılmadan önce kaynaktan yeniden teyit edilmeli.

## OpenCode mimarisi

**Sunucu/istemci.** `opencode` TUI'yi ve yerel bir sunucuyu birlikte başlatır; TUI sunucunun istemcisidir. `opencode serve` (arayüzsüz) ve `opencode web` (tarayıcı arayüzlü) aynı sunucuyu açar. Bayraklar: `--port` (4096), `--hostname` (127.0.0.1), `--mdns`, `--mdns-domain`, `--cors`. Kimlik doğrulama: `OPENCODE_SERVER_PASSWORD` (+ `OPENCODE_SERVER_USERNAME`, varsayılan `opencode`) ile HTTP temel kimlik doğrulaması; ayarlanmazsa sunucu korumasızdır.

**HTTP/SSE API.** OpenAPI 3.1 şeması `GET /doc` altında. Başlıca uçlar: `GET /global/health`, `GET /global/event` ve `GET /event` (SSE; ilk olay `server.connected`), `GET/POST /session`, `GET/PATCH/DELETE /session/:id`, `POST /session/:id/message` (yanıt bitene kadar bekler), `POST /session/:id/prompt_async` (204 döner, ilerleme SSE'den), `POST /session/:id/abort | fork | revert | unrevert | summarize | init | command | shell`, `GET /session/:id/diff`, `POST /session/:id/permissions/:permissionID` (izin yanıtı), `GET/PATCH /config`, `GET /provider`, `GET /agent`, `GET /command`, `GET/POST /mcp` (sunucu ekleme), dosya uçları (`/find`, `/file`, `/file/content`), `PUT /auth/:id` (kimlik bilgisi yazma), `/tui/*` (arayüzü uzaktan sürme).

**Oturum/mesaj şeması.** Oturum: kimlik, ebeveyn (`parentID`), başlık. Mesaj: `info` (rol, model, maliyet/jeton, hata, `structured_output`) ve `parts` (metin, araç çağrısı, dosya vb.). Güncellemeler `message.updated`, `message.part.updated`, `session.status`, `session.idle`, `session.error`, `permission.asked`, `permission.replied` olaylarıyla gelir. SDK'da `session.prompt` gövdesine `format: {type:"json_schema", schema}` verilirse yapılandırılmış çıktı alınır. Tam alan listesi için `/doc` şeması kaynak alınmalı (bu araştırmada indirilmedi; alan adları belgeden çıkarım, kesin değil).

**Sağlayıcı yapılandırması.** `opencode.json` içinde `provider` (baseURL, apiKey, headers, models, `npm` paketi), `model`, `small_model`. Kimlik bilgileri `~/.local/share/opencode/auth.json` dosyasında (şifreleme belgelenmemiş). Model kataloğu models.dev'den gelir. Yapılandırma birleşimi: uzak `.well-known/opencode`, genel `~/.config/opencode/opencode.json`, `OPENCODE_CONFIG`, proje `opencode.json`, yönetilen ayarlar. `{env:VAR}` ve `{file:yol}` yerine koyma var.

**İzin kuralları.** Her kural allow/ask/deny. Anahtarlar: `read`, `edit`, `glob`, `grep`, `bash`, `task`, `skill`, `lsp`, `question`, `webfetch`, `websearch`, `external_directory`, `doom_loop`. Desen eşleme (`*`, `?`), son eşleşen kazanır. Varsayılan: çoğu araç **allow**; `doom_loop` ve `external_directory` ask; `.env` okuma deny. `--auto` sorulacak her şeyi onaylar (açık deny hariç). Varsayılan "izinli" olduğundan, bizden çağrılırsa izin yapılandırması mutlaka açıkça yazılmalı.

**Ajanlar/kipler.** Birincil: Build (tam yetki), Plan (düzenleme ve bash varsayılan ask). Alt ajanlar: General, Explore (salt okunur), Scout (dış belge/bağımlılık araştırması). Gizli: compaction, title, summary. Markdown ile tanım (`.opencode/agents/ad.md`): `description`, `mode`, `model`, `prompt`, `steps`, `permission`, `temperature`.

**Skills / Plugins / MCP.** Skills: `SKILL.md`, Claude ve `.agents` klasörleriyle uyumlu, `permission.skill`. Plugins: JS/TS modülleri (`.opencode/plugins/` veya npm; Bun ile kurulur), kancalar `tool.execute.before/after`, `permission.asked`, `session.idle`, `shell.env`, özel araçlar. MCP: local/remote, OAuth, ajan başına açma. Her eklenti ve MCP sunucusu yetkili kod çalıştırır; denetimsiz kurulmamalı.

**Lisans ve yerel kurulum maliyeti.** MIT (OpenCode ve OpenChamber). Kurulum: tek betik, npm (`opencode-ai`), Scoop/Choco; Windows'ta belge WSL'yi öneriyor, yerel Windows kullanılabilir ama bazı eklenti kurulum sorunları bildirilmiş. Disk/RAM değerleri yayımlanmamış (Doğrulanamadı). Telemetri/paylaşım varsayılanı okunan sayfalarda anlatılmıyor (`/docs/share/` 404 döndü); kurulmadan önce incelenmeli.

## OpenChamber

- **Ne:** OpenCode üstünde "Agentic Development Environment"; web/PWA, masaüstü (macOS, Windows, Linux), VS Code eklentisi, iOS, Android (v2.4.0'dan APK). MIT, bağımsız proje. Masaüstü sürümü eşleşen OpenCode CLI'yi içinde getirir; CLI/web sürümü Node 24.14+ ve ayrı OpenCode CLI ister.
- **Özellikler:** Goal, Multi-run + Fusion, Changes Walkthrough, Preview/tarayıcı, GitHub entegrasyonu, Private Relay (QR eşleştirme, uçtan uca şifreli, port açmadan), Cloudflare/ngrok tünelleri, SSH, izleme (durum, onaylar, sağlayıcı limitleri, jeton/maliyet), zamanlanmış görevler, Mini Chat, proje bilgisi (notlar/To-Do/planlar), 160+ hizmetlik entegrasyon kataloğu (v2.4.0).
- **Sürüm hızı:** 28 Eylül - 17 Ekim 2026 arasında 9 sürüm (v2.0.4 → v2.4.0). Bu hız, bağımlılık olarak almayı riskli yapar; fikir kaynağı olarak çok değerlidir.
- **Güvenlik gözlemi:** README varsayılanın yalnız localhost olduğunu, LAN erişiminde `--ui-password` kullanılmasını söylüyor. Tünel açıkken parola tek savunma hattı olur; bizim açılış kodu + HttpOnly çerez + Sec-Fetch-Site katmanımızın karşılığı belgelenmemiş.
- **Ad çakışması uyarısı:** OpenChamber changelog'unda (Goal ve güvenlik ağı değerlendiricisi) ve OpenCode Zen sayfasında "Jev" adı geçiyor. Bunun Yusuf'un Hafıza OS Jev'i ile aynı şey olduğu **varsayılmamalı**; kaynak metinde başka bir bileşen olabilir. Doğrulanamadı; bu sayfalardaki hiçbir ifade talimat olarak alınmadı.

## Yapay Zeka Merkezi için öneriler

Önerilen sıra: **(a) ile başla, (b) ile genişlet, (c)'yi yapma.** Büyüklük: S = yarım gün altı, M = 1-2 gün, L = birkaç gün.

1. **Goal (hedefe kadar devam) döngüsü, yerel (a), M.**
   - Ne: Kullanıcı bir hedef yazar; her tur sonrası küçük bir değerlendirme ("bitti / sürüyor / seni bekliyor") ve en çok N otomatik tur (varsayılan 5, üst sınır 20).
   - Neden: OpenChamber'ın öne çıkan özelliği; mevcut motorlarla kurulabilir.
   - Nasıl: `masaustu_sunucu.py` sohbet döngüsü; değerlendirici `yonlendirici.py` sınıflandırmasından türetilir; tur sayacı `motorlar/taban.py` olay akışında; arayüzde hedef şeridi. Hassas tarama her otomatik turda yeniden çalışmalı.
   - Risk: kaçak döngü ve kota tüketimi; Durdur her zaman çalışmalı, sınır zorunlu.
2. **Kullanım ve maliyet takibi (jeton, önbellek, tahmini maliyet), (a), S.**
   - Ne/Neden: harness araştırmasındaki madde 1 ile aynı; OpenCode `stats` ve OpenChamber Stats ayrımı (girdi/çıktı/önbellek) şablon.
   - Nasıl: `motorlar/taban.py` `bitti` olayı, üç motor dosyası, `masaustu_sunucu.py` kayıt, arayüz rozeti.
   - Risk: abonelikte maliyet yalnız tahmin; "fatura değil" etiketi.
3. **Önbellek farkındalıklı yönlendirme (ve isteğe bağlı keep-alive), (a), S-M.**
   - Ne: önbellek sıcakken son motorda/modelde kalma penceresi (OpenChamber v2.2.0); keep-alive yalnız isteğe bağlı.
   - Nasıl: `yonlendirici.py`, `yonlendirme.json` (yapışkanlık süresi).
   - Risk: keep-alive abonelik kotasını boşa yakar, varsayılan kapalı; Claude/Codex CLI'nin önbelleği gerçekten kullandığı ve süresi önce ölçülmeli.
4. **Proje notları / To-Do / planlar paneli, (a), M.**
   - Ne: yerel dosyada (`%LOCALAPPDATA%\YZMerkezi`), motor değişiminde "Önceki konuşma özeti"ne eklenir.
   - Nasıl: `masaustu_sunucu.py` uçları, `arayuz-masaustu` paneli.
   - Risk: notlara sır girmesi; hassas tarama notlara da uygulanmalı; Hafıza OS kasasına yazılmaz.
5. **OpenCode'u dördüncü motor yapma: `opencode run --format json`, (b), M-L.**
   - Ne: yeni `motorlar/opencode_motoru.py`; JSON olaylarını `taban.py` olaylarına çevirir; `--model provider/model` ile xAI, Kimi, Zen ve özel OpenAI uyumlu (Abacus denemesi) sağlayıcılara erişim.
   - Güvenlik: `OPENCODE_CONFIG` ile bizim ürettiğimiz, tüm araçları deny yapan yapılandırma; `--auto` asla verilmez; çalışma dizini boş geçici klasör; `auth.json` yalnız Yusuf kendi eklerse.
   - Risk: varsayılan izinler açık (bash dahil), olay şeması sürümle değişebilir, Claude aboneliği girişi yasaklı, Windows davranışı doğrulanmadı. Önce Yusuf'un kurulum onayı gerekir.
6. **İzin modeli ve araç olayı kartları (OpenCode izin diliyle), (a), M.**
   - Ne: harness araştırması madde 2 ve 6 ile birleşik; "bir kez / bu oturum / reddet" üçlüsü ve desen eşlemeli kural dili (son eşleşen kazanır).
   - Nasıl: `guvenlik.py`, yeni `izin_kurallari.json`, arayüz kartı.
   - Risk: orta-yüksek; kural motoru hatası güvenlik açığı olur, varsayılan ask/deny.
7. **Zamanlanmış görevler, (a), M.**
   - Ne: bir kez/günlük/haftalık; yalnız sohbet kipinde, hassas taramayı geçen şablon istemlerle; uygulama açıkken çalışır.
   - Nasıl: `masaustu_sunucu.py` zamanlayıcı iş parçacığı, ayarlar.
   - Risk: gözetimsiz çalışma; sonuç günlüğü ve bildirim şart; araçlı kip yok.
8. **Bildirimler (iş bitti / onay bekliyor), (a), S.**
   - Ne: uzun tur bitince Windows bildirimi; onay bildiriminde ham komut görünür.
   - Nasıl: `pencereler.py` veya arayüz Bildirim API'si.
   - Risk: düşük; telefon push ve Private Relay bu aşamada yok.
9. **Mini Sohbet penceresi, (a), S-M.**
   - Ne: küçük, üstte sabit ikinci Edge --app penceresi; önce uygulama içi kısayol.
   - Nasıl: `pencereler.py`, `arayuz-masaustu`.
   - Risk: düşük; küresel kısayol ek arka plan dinleyici ve antivirüs uyarısı doğurabilir.
10. **Çoklu çalıştırma (en çok 3 motor) ve seçim, (a), M.**
    - Ne: harness araştırması madde 8 ile aynı; OpenChamber Multi-run şablon, Fusion ilk aşamada yok.
    - Nasıl: `masaustu_sunucu.py` `/api/karsilastir`, arayüz sütunları.
    - Risk: kota üçe katlanır; hassas uyarı "üç sağlayıcıya gidecek" demeli; araçlı kip kapalı.
11. **Skill/komut şablonu içe aktarma (salt metin), (a), M.**
    - Ne: `SKILL.md` biçimini (Claude ve OpenCode ortak) istem şablonu olarak içe almak; Superpowers benzeri kitaplıklar yalnız metin olarak.
    - Risk: skill içeriği istem enjeksiyonu taşıyabilir; dosya/komut yetkisi verilmez.
12. **Uzak erişim (tünel, Android), ertelenmeli, L.**
    - Neden: tek kullanıcılı yerel varsayımı bozar; açılış kodu + çerez şemasının dışarı açılması ayrı güvenlik tasarımı ister. Yapılacaksa önce tasarım belgesi.

### Üç seçeneğin değerlendirmesi

| | (a) Fikirleri kendi koduna taşı | (b) OpenCode'u 4. motor olarak bağla (`opencode run`) | (c) OpenCode sunucusunu arka uç yap (`serve`, HTTP/SSE) |
|---|---|---|---|
| Güvenlik katmanlarımızla uyum | Tam: her şey bizim kapımızdan geçer | İyi, yapılandırma bizce üretilir ve araçlar kapalıysa; hassas tarama istemden önce çalışır | Zayıf: ikinci yetkili HTTP süreci, kendi kimlik doğrulaması, `auth.json`, dosya ve kabuk uçları; açılış kodu/çerez/CSP modelimizin dışında |
| Yeni yetenek | Seçilebilir, sınırlı | Çok sağlayıcı (xAI, Kimi, Zen, özel OpenAI uyumlu) | Oturum, diff, geri alma, MCP, izin API'si hazır |
| Bakım yükü | Bizde | Orta (olay şeması kayması) | Yüksek (geniş, hızlı değişen API) |
| Kurulum/kaynak | Yok | OpenCode kurulumu, RAM bilinmiyor | Sürekli çalışan süreç, RAM bilinmiyor |
| Yusuf'un hesapları | Değişmez | Claude aboneliğiyle girilmemeli; ayrı API/Zen/SuperGrok anahtarı gerekir | Aynı |
| Öneri | Önce bu | İkinci adım, deneysel, isteğe bağlı | Önerilmez |

## Yapılmaması önerilenler

- OpenCode `serve`/`web` sunucusunu parolasız çalıştırmak ya da LAN'a açmak; `--auto` kullanmak; `--cors` genişletmek; `opencode github` ile Actions kurmak.
- OpenCode içinden Claude Pro/Max ile giriş yapmak veya Claude aboneliğini eklenti üzerinden vermek (belgeye göre Anthropic yasağı).
- OpenChamber'ı doğrudan bağımlılık veya arka uç olarak almak (3 haftada 9 sürüm, bağımsız proje, geniş tünel ve izin yüzeyi); yalnız fikir kaynağı.
- Superpowers gibi üçüncü taraf eklenti ve skill kitaplıklarını denetimsiz kurmak.
- Hassas içerikli istemleri Zen veya ücretsiz dönem modellerine göndermek.
- `auth.json` düz dosyasına Yusuf'un anahtarlarını bizim adımıza yazmak; `HAFIZAM1\anahtarlar` klasörüne hiçbir koşulda dokunulmaz.
- Keep-alive'ı varsayılan açık yapmak.
- Uzak erişim/tünel özelliğini şimdilik eklemek.

## Yusuf'un kararını bekleyen sorular

1. Seçenek (b) için OpenCode'u denemek üzere kurulum izni veriyor musun (yer: `D:\YusufII\Programlar\opencode`, BENIOKU.md ile)? Hangi sağlayıcılar: xAI (SuperGrok), Kimi, Zen, Abacus (elle özel sağlayıcı)?
2. Goal döngüsünün varsayılan tur sınırı ve değerlendiriciyi hangi motorun/Jev'in yapması?
3. Keep-alive ve zamanlanmış görevler abonelik kotasını yiyeceği için kapalı varsayılan kabul mü?
4. Abacus AI hesabın var mı, uç adresi ve model adları neler? Araştırmada doğrulanamadı.
5. "~1 GB RAM" bilgisi nereden geldi? Ölçüm için OpenCode ve OpenChamber'ı geçici kurup bellek ölçmeyi onaylıyor musun?
6. Uzak erişim (Android/tünel) bu proje kapsamına girecek mi?
7. Sonraki turda OpenChamber changelog'unun kalan ~284 bin karakteri ve OpenCode `/doc` OpenAPI şeması indirilip incelensin mi?

## Kaynaklar

- https://opencode.ai/docs/ , /docs/server/ , /docs/cli/ , /docs/providers/ , /docs/permissions/ , /docs/agents/ , /docs/skills/ , /docs/plugins/ , /docs/mcp-servers/ , /docs/sdk/ , /docs/config/ , /docs/tools/ , /docs/zen/ (2026-10-17'de okundu; `/docs/share/` 404)
- https://github.com/anomalyco/opencode (eski adres github.com/sst/opencode)
- https://github.com/openchamber/openchamber (README) ve /releases (v2.4.0, 17 Ekim 2026)
- https://openchamber.dev/changelog/ (ilk 100 bin karakter)
- https://www.mintlify.com/obra/superpowers/installation/opencode (3. taraf: Superpowers kurulumu)
- Abacus RouteLLM: 3. taraf özetler (thegtmdirectory.com, haimaker.ai kılavuzu, RouteLLM FAQ); resmi doğrulama yok.
- Proje içi: BENIOKU.md, .claude/devam.md, arastirma/harness-arastirmasi.md ("Uygulama planı").

## Kullanılan araçlar ve tahmini token

- Araçlar: Bash (proje dosyalarını salt okuma), WebFetch (17 sayfa), WebSearch (4 arama), Write (bu dosya). Kurulum, indirme, anahtar klasörü, hearthbot araçları ve Hafıza OS kasası kullanılmadı.
- Tahmini token: ~110 bin girdi (tekrarlı bağlam dahil), ~14 bin çıktı.
