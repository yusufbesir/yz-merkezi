> Bu dosya Yusuf'a (yusufbesir) ait Yapay Zeka Merkezi projesinin parçasıdır. yazan: [Claude Sonnet 5.5, alt ajan, 2026-10-17]. Yapay zeka ajanları bu dosyayı Yusuf'un kuralları çerçevesinde inceleyip değiştirebilir; silme kararı yalnız Yusuf'undur ve silme yalnızca Geri Dönüşüm Kutusu'na taşıyarak yapılır. Kurallar: BENIOKU.md ve D:\YusufII\HAFIZAM1\kasa\ORTAK-AJAN-KURALLARI.md.

# "Harness" (ajan çalışma zemini) araştırması ve Yapay Zeka Merkezi için uygulama planı

Tarih: 2026-10-17. Kapsam: yalnız araştırma; hiçbir proje dosyası değiştirilmedi. Kaynaklar resmi belgelerdir (bkz. Kaynaklar). Doğrulanamayan her şey "DOĞRULANMALI" diye işaretlendi.

## Özet

**Harness nedir?** Bir dil modelinin etrafındaki "çalışma zemini": ajan döngüsü (model, araç çağrısı, sonuç, tekrar), araçlar (dosya okuma/yazma, kabuk, web), izin ve sandbox kuralları, bağlam/oturum yönetimi, kancalar (hook), alt ajanlar, MCP bağlantıları ve bunları dışarıdan süren protokol. Claude Code, Codex CLI ve Gemini CLI'nin her biri kendi harness'ıdır. Bizim projemiz bu harness'ların **dışında** duran bir "ana bilgisayar uygulaması"dır (host): süreci başlatır, olay akışını okur, izinleri ve çıktıyı kullanıcıya gösterir.

**Bizim durum.** `motorlar/` paketi üç harness'ı da "tek atımlık sohbet motoru" olarak kullanıyor: Claude `claude -p ... --tools ""`, Codex `codex exec --json --sandbox read-only`, Gemini `node gemini.js --output-format stream-json --approval-mode default`. İstem stdin'den gidiyor, olaylar satır satır okunup dört-beş olay türüne (baslangic, durum, parca, bitti, hata) indirgeniyor (`motorlar/taban.py:7-11`). Bu, güvenli ve basit bir temel; ancak harness'ların sunduğu şu zenginliklerin hepsi şu an **atılıyor**:

1. Kullanım ve maliyet alanları (Claude `result.total_cost_usd`, `usage`, `modelUsage`; Codex `turn.completed.usage`; Gemini `result.stats`).
2. Araç çağrısı olayları (yalnız "araç kullanıyor…" metni var; ne çalıştı, ne döndü görünmüyor).
3. İzin akışı (Claude'da `dontAsk` ile her şey sessizce reddediliyor; arayüze soru taşınmıyor).
4. Çalışma kipi (araçlar tümden kapalı; "salt okunur araştır" ya da "çalışma klasöründe düzenle" kipleri yok).
5. Çift yönlü akış (her mesaj yeni süreç; ara müdahale, kuyruk, kesinti yok).

Aşağıdaki plan bunları küçük ve güvenli adımlarla açar; ilk üç madde yalnız `motorlar/*.py` ve bir sunucu süzgecinde değişiklik gerektirir ve varsayılan davranışı değiştirmez.

**Önemli dış bulgular (bizi doğrudan etkileyenler):**

- Anthropic belgesi: üçüncü taraf geliştiriciler, izin almadıkça kendi ürünlerinde claude.ai girişi ya da oran sınırı sunamaz; "Claude Code" adı/görünümü üçüncü taraf ürün için yasak. Bizim durumumuz Yusuf'un kendi bilgisayarında kendi hesabıyla tek kullanıcılı yerel kullanım; ürün olarak dağıtılırsa bu kural önem kazanır. Arayüzde "Claude" yazması uygundur, "Claude Code" markasını taklit etme.
- Codex belgesi: app-server kimlik doğrulamasının ticari ya da barındırılan hizmetler için hiç izinli olmadığı yazıyor; yine yalnız kişisel yerel kullanım için sorun yok.
- Gemini belgelerinde: 18 Haziran 2026 itibarıyla ücretsiz katman ve Google One kullanıcıları için Gemini CLI'nin yerini Antigravity CLI aldığı yazıyor. `motorlar/gemini_motoru.py` bu geçişten etkilenebilir (Yusuf'un hesabı hangi katmandaysa); ayrı bir izleme maddesi eklendi.

## Claude Code harness ayrıntıları

### 1. Agent SDK ile `claude -p` farkı

- Agent SDK (Python `claude-agent-sdk`, TypeScript `@anthropic-ai/claude-agent-sdk`) "Claude Code ikilisini çalıştıran bir kütüphane"dir; aynı araçları, ajan döngüsünü, izinleri, oturumları, kancaları ve alt ajanları sunar. Belgeye göre başka bir dilden aynı döngü `claude -p` alt süreci ile sürülür. Yani SDK, CLI'nin üstüne yazılmış sarmalayıcıdır; bizim `motorlar/claude_motoru.py` aslında kendi küçük SDK'mızdır.
- SDK'nin ek getirisi: `canUseTool` geri çağrısı (izin sorusu), `interrupt()`, `setPermissionMode()`, `setModel()`, yerel mesaj nesneleri. Bunlar CLI'nin `--input-format stream-json` altında stdin/stdout üzerinden konuştuğu `control_request`/`control_response` zarfları ile gerçekleşir (zarf: `{ "type": "control_request", "request_id", "request": {...} }`; `canUseTool` istemi bu `request_id`'yi taşır ve yanıt aynı kimliği yankılamak zorundadır; yanıt verilmezse araç çağrısı sonsuza dek bekler). Bu tel protokolü SDK referansında yalnız parça parça geçer; resmi kararlı bir CLI sözleşmesi olarak belgelenmemiştir. **DOĞRULANMALI** (sürüm kayması riski yüksek, `capabilities` dizisiyle özellik algılama önerilir: `interrupt_receipt_v1`, `interrupt_cancel_queued_v1`, `mcp_read_resource_v1`).
- Python SDK stdlib değildir; projemiz yalnız standart kütüphane kullandığı için SDK'yi doğrudan almak yerine CLI protokolünü kendimiz konuşmak (ya da `-p` ile sürmek) tutarlıdır.

### 2. Başsız (headless) bayraklar

| Bayrak | Anlamı | Bizde |
| :- | :- | :- |
| `-p`, `--output-format stream-json --verbose` | Olay akışı (satır başına JSON). `--verbose` stream-json için gerekli | var |
| `--include-partial-messages` | `stream_event` ile jeton jeton `content_block_delta` | var |
| `--input-format stream-json` | stdin'den birden çok kullanıcı mesajı, çift yönlü oturum; `--replay-user-messages` onay için | yok |
| `--permission-mode` | `default`, `acceptEdits`, `plan`, `auto`, `dontAsk`, `bypassPermissions` (`manual` takma ad) | `dontAsk` sabit |
| `--allowedTools` / `--disallowedTools` | Ön onaylı araçlar / kaldırılan araçlar (`Bash(git diff *)` kural söz dizimi) | yok |
| `--tools` | Yerleşik araç kümesini kısıtlar; `""` hepsini kapatır | `""` sabit |
| `--mcp-config`, `--strict-mcp-config` | MCP sunucuları; strict yalnız verilenleri kullanır | strict var, config yok |
| `--permission-prompt-tool` | Başsız kipte izin istemini bir MCP aracına yönlendirir | yok |
| `--permission-prompts none` | Kimse yanıtlamayacaksa istemleri reddeder (v2.1.259+) | yok |
| `--resume ID` / `--continue` / `--fork-session` / `--session-id UUID` | Oturum sürekliliği | `--resume` var |
| `--append-system-prompt(-file)` / `--system-prompt(-file)` | Sistem istemi ekleme/değiştirme | append var |
| `--max-turns`, `--max-budget-usd` | Tur ve bütçe sınırı (yalnız -p) | yok |
| `--fallback-model a,b` | Aşırı yükte yedek model zinciri | yok |
| `--agents '{json}'` | Komut satırında alt ajan tanımı | yok |
| `--add-dir` | Ek çalışma dizini | yok |
| `--settings`, `--setting-sources` | Ayar dosyası/JSON; hangi kaynakların yükleneceği | sources var |
| `--no-session-persistence` | Oturumu diske yazmaz (devam ettirilemez) | yok |
| `--include-hook-events` | Kanca yaşam döngüsü olaylarını akışa katar | yok |
| `--forward-subagent-text` | Alt ajan metin/düşünce bloklarını akışa katar | yok |
| `--json-schema` | Şemaya uyan yapılandırılmış çıktı (`structured_output`) | yok |
| `--bare` | Kancalar, MCP, CLAUDE.md vb. keşfini atlar; **abonelik girişini okumaz, ANTHROPIC_API_KEY gerekir** | kullanılamaz (doğru karar, `claude_motoru.py:385`) |
| `--restricted`, `--safe-mode` | Kısıtlı / tüm özelleştirmeler kapalı kip | yok |

Çıkış kodu: başarıda 0, hatada sıfır dışı. SIGTERM ile durdurulursa 143 ve tur kayıtsız kalır; turu düzgün bitirmek için SIGINT ya da SDK `interrupt()` gerekir. Bizim `sureci_durdur` (`taban.py:67`) Windows'ta `taskkill /T /F` ile zorla öldürüyor; yarım tur oturum dosyasına "kesintiye uğramış" olarak girer (resume güvenli, ama son tur yok sayılır).

### 3. Olay şeması (stream-json, çıktı)

Satır başına bir JSON; `type` alanına göre:

- `system` / `subtype: init`: `session_id`, `model`, `tools`, `mcp_servers [{name,status}]`, `permissionMode`, `cwd`, `slash_commands`, `skills`, `plugins`, `claude_code_version`, `apiKeySource`, `capabilities`. Ayrıca `system/api_retry` (alanlar: `attempt`, `max_retries`, `retry_delay_ms`, `error_status`, `error`) ve `permission_denied` sistem iletileri.
- `stream_event`: `event` ham Anthropic akış olayıdır (`message_start`, `content_block_start`, `content_block_delta` {`text_delta`, `thinking_delta`, `input_json_delta`}, `message_delta` {usage}, `message_stop`).
- `assistant`: `message` (Anthropic mesajı: `id`, `model`, `content` blokları `text`/`tool_use`{id,name,input}/`thinking`, `usage`), `parent_tool_use_id` (alt ajan iletilerinde dolu).
- `user`: araç sonuçları (`tool_result` blokları, `tool_use_id`, `content`, `is_error`).
- `result`: `subtype` (`success` | `error_max_turns` | `error_during_execution` | `error_max_budget_usd` | `error_max_structured_output_retries`), `is_error`, `result` (yalnız success), `errors[]`, `session_id`, `duration_ms`, `duration_api_ms`, `num_turns`, `stop_reason`, `total_cost_usd`, `usage` {`input_tokens`, `output_tokens`, `cache_creation_input_tokens`, `cache_read_input_tokens`}, `modelUsage` {model: {inputTokens, outputTokens, cacheReadInputTokens, cacheCreationInputTokens, costUSD, costBasis}}, `permission_denials [{tool_name, tool_use_id, tool_input}]`.

Maliyet ve kullanım notları (resmi "Track cost and usage" sayfasından):

- `total_cost_usd` ve `costUSD` **istemci tarafı tahmindir**, fatura değildir; abonelikte zaten kota/limit mantığı farklıdır. Arayüzde "tahmini" etiketiyle gösterilmeli; hiçbir mali karar buna bağlanmamalı.
- Resume edilen oturumda `total_cost_usd` oturumun **toplamını** verir (v2.1.277+); sonuçları toplamak çift sayım olur. Her çağrının farkını göstermek istersek önceki toplamı çıkarmalıyız.
- Ara iletilerdeki `output_tokens` yer tutucudur; gerçek çıktı jeton sayısı `result.usage` içindedir. Alt ajanlar `usage` alanında sayılmaz, `total_cost_usd` ve `modelUsage` içinde sayılır.
- Hata sonuçları da kullanım taşır (çökmede sıfırlanmış olabilir).

### 4. İzin sistemi ve izin istemini arayüze taşıma

Değerlendirme sırası (resmi): kancalar, ret kuralları, sor kuralları, izin kipi, izin kuralları, `canUseTool`. `dontAsk` kipinde 6. adım atlanır ve istem gerektiren her şey reddedilir (bizim bugünkü durum: araç yok olduğundan etkisi yok).

Başsız kipte izin istemini arayüze taşımanın üç yolu vardır:

- **A. `--permission-prompt-tool <mcp araç adı>`**: Claude, istem gerektiren her araç çağrısında bu MCP aracını çağırır (girdi: araç adı ve girdisi; dönüş: JSON ile `behavior: "allow"` + `updatedInput` ya da `behavior: "deny"` + `message`). MCP sunucusu `--mcp-config` ile verilir ve Claude ilk tur öncesi bağlanmasını `MCP_TIMEOUT` (varsayılan 30 sn) kadar bekler. Dönüş şeklinin ayrıntısı bu araştırmada resmi sayfadan doğrulanamadı (CLI başvurusu yalnız bayrağı tanımlıyor; `allow` sonucunun `requiresUserInteraction` MCP araçları için deny'a çevrildiği belirtilmiş). **DOĞRULANMALI.** Stdlib ile MCP stdio sunucusu yazmak mümkündür (JSON-RPC 2.0, `initialize`, `tools/list`, `tools/call`) ama bu sunucunun, çalışan ana sunucumuza (token'lı 127.0.0.1) bir köprü kurması gerekir.
- **B. Kanca (hook) ile**: `PermissionRequest` kancası bir izin istemi çıktığında çalışır ve `hookSpecificOutput.decision.behavior` = `allow`/`deny` döndürür; kancalar komut, **HTTP uç noktası**, MCP aracı, LLM istemi ya da alt ajan olabilir ("HTTP hooks receive it as the POST body"). `--settings '{"hooks":{...}}'` ile oturuma özel verilebilir. Bu, stdlib bir sunucu için en az sürtünmeli yol olabilir: kanca doğrudan `http://127.0.0.1:PORT/api/izin` adresine POST eder, sunucu soruyu arayüze akıtır, kullanıcı yanıtını bekler, yanıtı döndürür. Kanca istekleri başlık eklemeyi (belirteç) destekliyor mu? **DOĞRULANMALI.** Ayrıca `PreToolUse` kancasının `defer` kararı ve `permissionDecision: ask/allow/deny` desteği var; "tüm araç çağrıları için geçerli olması gereken denetim PreToolUse ile yapılır" (kancalar her şeyden önce çalışır, ret `bypassPermissions`'ta bile geçerlidir).
- **C. Çift yönlü stream-json (`--input-format stream-json`)**: SDK'nin `canUseTool` yaptığı yöntem: `control_request` (subtype `can_use_tool`) stdout'ta gelir, ana bilgisayar `control_response` ile stdin'e yanıt yazar. En zengin yol (kalıcı ilke önerileri `suggestions`, `AskUserQuestion` soruları, `interrupt`) ama tel biçimi resmi olarak kararlı belgelenmemiş; sürüme bağlı kalır. **DOĞRULANMALI** (Python SDK kaynağı okunabilir).

`AskUserQuestion` aracı da aynı kanaldan gelir (1-4 çoktan seçmeli soru); `--tools` listesi verilirse bu araç listeye eklenmelidir yoksa Claude soru soramaz.

### 5. Kancalar (hooks)

Olaylar: oturum (`SessionStart`, `SessionEnd`, `Setup`), tur (`UserPromptSubmit`, `Stop`, `StopFailure`), araç (`PreToolUse`, `PostToolUse`, `PostToolUseFailure`, `PostToolBatch`, `PermissionRequest`, `PermissionDenied`), alt ajan/görev, bağlam (`PreCompact`, `InstructionsLoaded`, `FileChanged`...), `Notification`, `Elicitation`, `PreModelSwitch` vb. Girdi stdin JSON'u: `session_id`, `transcript_path`, `cwd`, `permission_mode`, `hook_event_name`, `tool_name`, `tool_input`, `tool_use_id`. Çıkış: kod 0 + JSON (karar), kod 2 = engelle (stderr gerekçe), diğerleri engellemez. Ayar konumları: `~/.claude/settings.json`, `.claude/settings.json`, `.claude/settings.local.json`, yönetilen politika, eklenti, skill/alt ajan başlığı.

**Bizim için kritik risk:** `-p` kipi, çalışma klasöründeki proje kancalarını ve `.mcp.json` sunucularını **güven penceresi olmadan** çalıştırır. Mevcut komut bunu `--setting-sources project,local` ile **kullanıcı** kancalarını (örn. Yusuf'un kasa kancaları) kapatacak şekilde ayarlamış, ama proje/yerel kaynaklar açık. Çalışma klasörümüz `%LOCALAPPDATA%\YZMerkezi\calisma` ve içerik üretmediğimiz için pratikte boş; **kullanıcı dışarıdan bir klasör seçtirmeye başladığımızda** (madde 3) bu klasördeki `.claude/settings.json`, `.mcp.json` kodu çalıştırabilir. Bu yüzden klasör seçimi eklenirse kaynaklar `local` ya da boş bırakılmalı ya da `--safe-mode`/`--restricted` değerlendirilmeli.

### 6. MCP, alt ajanlar, skill'ler, `claude agents`

- `--mcp-config <dosya|json>` ile MCP sunucuları; `--strict-mcp-config` diğer tüm MCP kaynaklarını yok sayar (bizde var). `claude mcp ...` alt komutları sunucu yönetir. Kanıtlanmış güvenli kullanım: yalnız Yusuf'un onayladığı sunucular, `--allowedTools "mcp__sunucu__arac"` ile tek tek ön onaylı.
- Alt ajanlar: `--agents '{"gozden-gecirici":{"description":...,"prompt":...}}'` ya da `.claude/agents/`. İleti akışında `parent_tool_use_id` ile ayrılır; metin/düşünce bloklarını görmek için `--forward-subagent-text`. Alt ajanlarda `AskUserQuestion` yok.
- Skill'ler: `--setting-sources`'ta `user` varsa `~/.claude/skills` yüklenir. Yusuf'un kullanıcı kancaları ve skill'leri (Hafıza OS, Jev) sohbet motorunda **kasıtlı kapalı**; açmak ayrı karardır.
- `claude agents`: arka plan oturumlarını izleyen/dağıtan "agent view" arayüzünü açar (interaktif terminal gerekir); `claude agents --json` etkin oturumları JSON döker; `claude attach/logs/stop/respawn/rm <id>` alt komutları vardır. Bizim için doğrudan kullanışlı değil (arka plan oturumu sistemi ayrı bir süpervizör süreci gerektirir), ama "uzun görevler" için ileri bir seçenek.

### 7. Oturum dosyaları

Dökümler `~/.claude/projects/<çalışma-dizini, alfanümerik olmayanlar '-'>/<oturum-id>.jsonl` altındadır (varsayılan saklama 30 gün, `cleanupPeriodDays`). `claude -p` ve SDK oturumları seçicide ve `--continue`'da görünmez ama `--resume <id>` ile (başka klasörden bile) devam ettirilir; `--resume` bir `.jsonl` mutlak yolunu da kabul eder. Biçim dahilidir ve sürümler arası değişir; elle ayrıştırma önerilmez. Resume'da yeniden verilmesi gerekenler: `--mcp-config`, `--settings`, `--add-dir`, `--fallback-model`; sistem istemi ilk istekte kaydedilir ve sonraki çağrılarda aynı kalır (yenilemek için `--system-prompt-snapshot off`). `CLAUDE_CONFIG_DIR` + `CLAUDE_CODE_PROJECT_DIR_NAME` ile depolama taşınabilir (alt süreç ortamına `taban._ortam` üzerinden verilebilir).

Önemli gizlilik sonucu: hassas bilgi içeren ve "Yine de gönder" ile onaylanmış mesajlar da `~/.claude/projects` altına düz metin yazılır. `--no-session-persistence` bunu engeller ama o oturum devam ettirilemez.

## Codex

Kaynak notu: `developers.openai.com/codex/*` adresleri `learn.chatgpt.com/docs/*` adresine kalıcı yönlendiriyor; içerik OpenAI belgesidir (kod yorumundaki bağlantıyla uyumlu), yönlendirme başlığı doğrulanmamış olarak not edildi.

- **`codex exec --json`**: stdout JSONL. Olaylar: `thread.started{thread_id}`, `turn.started`, `item.started/updated/completed`, `turn.completed{usage}`, `turn.failed{error}`, `error`. Öğe türleri: ajan iletisi, akıl yürütme, komut çalıştırma, dosya değişikliği, MCP araç çağrısı, web araması, plan güncellemesi. `turn.completed.usage`: `input_tokens`, `cached_input_tokens`, `output_tokens`, `reasoning_output_tokens`. Maliyet alanı **yok** (yalnız jeton). İlerleme stderr'e, son ileti stdout'a gider (`--json` yokken).
- **Sandbox**: `--sandbox read-only` (varsayılan) | `workspace-write` | `danger-full-access`; onay politikası `on-request` | `never` (`untrusted` artık desteklenmiyor); `approvals_reviewer = auto_review` uygun istemleri bir gözden geçirici ajana verir; `--approve-for-me` otomatik gözden geçirme + workspace-write. `--full-auto` **kaldırıldı** (yerine `--sandbox workspace-write`). Windows'ta PowerShell için yerel sandbox. `sandbox_workspace_write.writable_roots` ile yazılabilir kökler.
- **Diğer**: `--output-schema <dosya>`, `-o/--output-last-message <dosya>`, `--ephemeral` (oturum dosyası yok), `--ignore-user-config`, `--ignore-rules`, `--skip-git-repo-check`, `codex exec resume <ID|--last>`. `-c anahtar=değer` geçersiz kılmaları bu sayfada belgelenmemiş ama bizim kodumuz `exec resume` için kullanıyor (`codex_motoru.py:115`) ve çalışıyor olarak not edilmiş.
- **`codex mcp`**: MCP sunucusu yönetimi alt komutu var; `required = true` işaretli sunucu başlamazsa çalıştırma hata ile çıkar. Ayrıntı bu araştırmada doğrulanmadı. **DOĞRULANMALI.**
- **`codex app-server`** (JSON-RPC 2.0, `jsonrpc` başlığı atlanır): taşıma stdio JSONL (varsayılan), WebSocket (deneysel), Unix soketi. Her bağlantı `initialize` + `initialized` ile başlar. Yöntemler: `thread/start`, `thread/resume`, `thread/fork`, `turn/start`, `turn/steer` (etkin tura girdi ekler), `turn/interrupt` (tur `interrupted` biter). Bildirimler: `turn/started`, `item/started`, `item/completed`, `item/agentMessage/delta`, `thread/tokenUsage/updated` (yük şeması doğrulanmadı), `turn/completed`. Onay: sunucu kaynaklı istek `item/commandExecution/requestApproval` (alanlar `itemId`, `threadId`, `turnId`, `reason`, `command`, `cwd`, `availableDecisions`...) ve `item/permissions/requestApproval`; yanıt kararları `accept`, `acceptForSession`, `decline`, `cancel`. Şemayı sürüme özel üretmek için `codex app-server generate-json-schema --out ./sema` (ve `generate-ts`). Giriş: `account/login/start` (apiKey, chatgpt, chatgptDeviceCode...). Deneysel alanlar `capabilities.experimentalApi: true` ister. Uyarı: belgeye göre app-server kimlik doğrulaması ticari/barındırılan hizmetler için izinli değil.
- Bizim karşılığımız: `codex exec --json` tek atımlık; onayları arayüze taşımak için `app-server` doğru araç (ama protokol büyük ve sürümle değişiyor; şema üretici ile sürüm uyumu otomatikleştirilebilir).

## Gemini CLI

- **Başsız**: stdin/stdout boru olunca ya da `-p` ile. `--output-format text|json|stream-json`. `json` tek nesne: `response`, `stats`, `error`. `stream-json` olayları: `init` (oturum kimliği ve model), `message` (kullanıcı/asistan parçaları), `tool_use`, `tool_result`, `error` (kritik olmayan uyarılar), `result` (sonuç, toplu istatistik, model başına jeton dökümü). Çıkış kodları: 0 başarı, 1 genel/API hatası, 42 girdi hatası, 53 tur sınırı (bizim kod ayrıca 41 ve 55 için yorum yazıyor, `gemini_motoru.py:149-156`; bunlar bu sayfada belgelenmemiş, mevcut gözleme dayalı).
- **Onay kipleri**: `--approval-mode default | auto_edit | yolo | plan`; `--yolo` kullanımdan kalkmış (yerine `--approval-mode=yolo`). Başsız kipte politika motorunda `ask_user` kararı **deny** sayılır (bizde bu yüzden araçlar fiilen çalışmaz). `--allowed-tools` kullanımdan kalkmış; yerine **Policy Engine**: `~/.gemini/policies/*.toml` içinde `[[rule]]` blokları (`toolName`, `decision = allow|deny|ask_user`, `priority`, `argsPattern`, `commandPrefix`, `mcpName`, `modes`, `interactive`, `denyMessage`); yönetici politikaları `--admin-policy` ile; çalışma alanı katmanı şu an çalışmıyor diye belgelenmiş.
- **MCP**: `--allowed-mcp-server-names`; uzantılar (`gemini extensions ...`) ve skill'ler (`gemini skills ...`) alt komutları var.
- **Oturum**: `~/.gemini/tmp/<proje_hash>/chats/` altında saklanır, projeye (çalışma klasörüne) bağlıdır; `--resume` (`latest`, dizin no ya da tam UUID), `--list-sessions`, `--delete-session`; saklama 30 gün (`general.sessionRetention`).
- **ACP**: Agent Client Protocol modu (stdio JSON-RPC 2.0): `initialize`, `authenticate`, `newSession`, `loadSession`, `prompt`, `cancel`, `setSessionMode` (onay düzeyi), model değiştirme. Başlatma bayrağı belgede `--acp` ve başka sayfada `--experimental-acp` olarak geçiyor (tutarsız). **DOĞRULANMALI** (kurulu sürümde `gemini --help`). İzin isteği akışı bu sayfada anlatılmıyor; ACP şartnamesine bakılmalı.
- **Durum notu**: belgeler, ücretsiz katman ve Google One kullanıcıları için Gemini CLI'nin 18.06.2026'dan itibaren Antigravity CLI ile değiştirildiğini ve Gemini 4 Argon için optimize edilmediğini belirtiyor.

## Mevcut motorlarımızla fark analizi

Genel mimari (`motorlar/taban.py`): tek `Motor.sor()` üreticisi, süreç başına bir tur; dört okuyucu iş parçacığı (stdin yazıcı, stdout, stderr, ana döngü); zaman aşımı 60 sn ilk satır / 600 sn toplam (`taban.py:42-43`); iptal `taskkill /T /F` (`taban.py:67-85`); sonuç olayı `bitti` yalnız `oturum`, `metin`, `model`, `sure` taşır (`taban.py:362-363`). Sunucu tarafında `masaustu_sunucu.py:1187` satırındaki `elif tur != "durum": continue` süzgeci, bilinen dört tür dışındaki **her yeni olay türünü akıştan atar**; yeni olay türleri eklemek bu süzgecin güncellenmesini ve kalıcı kayıt alanlarının genişletilmesini gerektirir.

| Konu | Claude (`claude_motoru.py`) | Codex (`codex_motoru.py`) | Gemini (`gemini_motoru.py`) | Eksik / not |
| :- | :- | :- | :- | :- |
| Komut | satır 447-457: `-p --output-format stream-json --verbose --include-partial-messages --permission-mode dontAsk --strict-mcp-config --setting-sources project,local [--model] [--resume] --append-system-prompt --tools ""` | satır 113-123: `exec [resume] --json --skip-git-repo-check --sandbox read-only` | satır 89-95: `--output-format stream-json --skip-trust --approval-mode default [-m] [--resume]` | Kip sabit; ayar yok |
| Kullanım/maliyet | `result` işleniyor ama `total_cost_usd`, `usage`, `modelUsage`, `num_turns` **okunmuyor** (satır 492-501) | `turn.completed` yalnız `bitti` işaretliyor, `usage` atılıyor (satır 166-167) | `result.stats` yalnız model adı için bakılıyor (satır 135-139); jeton verisi atılıyor | `bitti` olayında `kullanim` yok |
| Araç olayları | `assistant.content[].tool_use` ve `user.tool_result` hiç işlenmiyor (araçlar kapalı olduğu için sorun yok) | `command_execution`, `mcp_tool_call`, `web_search`, `file_change` tek bir "araç kullanıyor…" durum metnine indirgeniyor (satır 162-163); komut, çıktı, çıkış kodu, durum atılıyor. Not: salt okunur sandbox'ta Codex yine de komut **çalıştırabiliyor**, yani bu bilgi bugün bile değerli | `tool_use`/`tool_result` yine tek durum metni (satır 122-123) | Arayüzde ne çalıştığı görünmüyor |
| İzin | `dontAsk` + araçsız: sorulacak şey yok | sandbox `read-only`; onay politikası verilmiyor (varsayılan); `exec` başsız olduğundan onay istemi çıkarsa takılma riski belgelenmedi | `default` kipi başsızda `ask_user` = deny | İzin istemi arayüze taşınmıyor |
| Oturum | `session_id` → `--resume` (satır 462-463, 453-454) | `thread_id` → `exec resume` (satır 139-142, 114-121) | `init.session_id` → `--resume` (satır 107-109, 93-94) | `--session-id` ön atama, `--fork-session`, kalıcılık kapatma yok |
| Sistem istemi | `--append-system-prompt` | istemin başına ekleme | istemin başına ekleme | Codex/Gemini'de gerçek sistem istemi yok (aynı) |
| Düşünme/akış | `thinking_delta` → durum (satır 476-477); parça başına akış | öğe `text` artışı → parça | `message` (delta) → parça | Düşünce metni gösterilmiyor (bilinçli olabilir) |
| Hata | `result` hata alt türleri tek mesaja iniyor (satır 493-498); `permission_denials` ve `api_retry` yok sayılıyor | `turn.failed`/`error` ele alınıyor (satır 168-175) | `error`/`result.status` ele alınıyor (satır 124-139) | `error_max_turns`, `error_max_budget_usd` ayrımı yok |
| Süreç yönetimi | zorla öldürme; SIGINT/`interrupt` yok | aynı | aynı | Düzgün iptal yok (tur yarım kalır) |
| MCP/alt ajan/skill | `--strict-mcp-config` ile MCP kapalı, kullanıcı kaynakları kapalı | yok | yok | Opt-in mekanizma yok |
| Test | `testler/test_motorlar.py`, `testler/sahte_motorlar/` sahte betikler | | | Yeni olay biçimleri için sahte betik genişletilmeli |

Genel değerlendirme: bugünkü tasarım "güvenli sohbet" hedefi için tutarlı. Eksikler harness'ın sunduğu **gözlemlenebilirlik** (kullanım, araç olayları, izin) ve **kontrol** (kip, sınırlar, kesinti) alanlarında. Çift yönlü oturum ve izin akışı en büyük mimari değişikliklerdir; ilk üç madde bunlardan bağımsızdır.

## Uygulama planı

Öncelik sırası güvenlik ve küçüklük ölçütüne göredir. Büyüklük: S = yarım gün altı, M = 1-2 gün, L = birkaç gün.

**1. Kullanım ve maliyet alanlarını `bitti` olayına taşı (S).**
- Ne: `bitti` olayına `kullanim: {girdi, cikti, onbellek_okuma, onbellek_yazma, maliyet_usd|None, tur_sayisi, sure_api}` ekle. Claude: `result.usage`, `total_cost_usd`, `modelUsage`, `num_turns`, `duration_api_ms`. Codex: `turn.completed.usage` (`input_tokens`, `cached_input_tokens`, `output_tokens`, `reasoning_output_tokens`; maliyet yok). Gemini: `result.stats` (model başına jeton).
- Neden: harness'ın en ucuz zenginliği; çoklu model karşılaştırması ve bütçe farkındalığı için temel. Belge uyarısı: maliyet tahmindir; resume'da toplam kümülatiftir (önceki toplam çıkarılmalı).
- Dosyalar: `motorlar/taban.py` (bitti olayı, `durum["kullanim"]`), `claude_motoru.py:492-501`, `codex_motoru.py:166-167`, `gemini_motoru.py:129-139`; `masaustu_sunucu.py` (bilinen alanları kayda geçirme, ~1180 ve kayıt kısmı); `arayuz-masaustu` (yanıt rozetinde "~1,2 bin jeton · tahmini $0,01" ipucu); testler.
- Risk: düşük. Abonelikte `total_cost_usd` yanıltıcı olabilir ("tahmini, fatura değil" etiketi). Mevcut kayıt biçimi geriye uyumlu kalmalı (eksik alan serbest).

**2. Araç çağrısı olaylarını arayüzde göster: yeni `arac` olay türü (S-M).**
- Ne: `{"tur":"arac","kimlik","ad","ozet","durum":"basladi|bitti|hata","cikti_ozeti"}`. Codex `item.*` (command_execution: `command`, `aggregated_output`, `exit_code`, `status`; file_change; mcp_tool_call; web_search), Gemini `tool_use`/`tool_result`, Claude (madde 3-4 açılınca) `assistant.tool_use` + `user.tool_result`. Sohbette rozetin altında daraltılabilir tek satırlık "çalıştırılan komutlar" listesi.
- Neden: Codex bugün salt okunur sandbox'ta bile komut çalıştırıyor; kullanıcı ne olduğunu görmeli. İzin planının görsel altyapısıdır.
- Dosyalar: üç motor `_satir_isle`; `taban.py:323-338` (olay süzgeci yeni türü geçirmeli); **`masaustu_sunucu.py:1187` süzgeci** (yeni tür geçsin, kalıcı kayda da girsin); arayüz sohbet bileşeni; `testler/sahte_motorlar/`.
- Risk: orta. Araç çıktıları gizli veri içerebilir: gösterimden ve kayıttan önce `hassas.tara/ornek_maskele` ile maskelenmeli, uzunluk sınırlanmalı (örn. 2 KB), JSON olarak değil metin olarak çizilmeli (güvenli DOM, `textContent`). Modelden gelen komut metni arayüze güvenilmez veri olarak girer.

**3. Çalışma kipi ayarı: Sohbet / Salt okunur araştır / Klasörde düzenle (M).**
- Ne: Ayarlar'da motor-bağımsız "kip" seçeneği; her motorda karşılığı:
  - Sohbet (bugünkü): Claude `--tools "" --permission-mode dontAsk`; Codex `read-only`; Gemini `default`.
  - Salt okunur araştır: Claude `--tools "Read,Grep,Glob" --permission-mode dontAsk` (+ `--add-dir` seçilen klasör, `--disallowedTools "Bash"`); Codex `read-only` + seçilen klasör `cwd`; Gemini `plan` (salt okunur araştırma kipi).
  - Klasörde düzenle: Claude `--permission-mode acceptEdits` + `--tools "Read,Grep,Glob,Edit,Write"`; Codex `--sandbox workspace-write`; Gemini `auto_edit` (başsızda diğer yazma araçları reddedilir).
  Çalışma klasörü seçici ayrı; varsayılan kip Sohbet kalır. Yürütücü komut (Bash) bu aşamada **verilmez**.
- Neden: harness'ın asıl değeri araçlardır; ama kontrol bizde olmalı. Bayrakların hepsi resmi belgede var.
- Dosyalar: `_komut(...)` imzasına `kip`, `klasor` eklenir (`taban.py:213`, `Motor.sor` seçenekleri `taban.py:234`); üç motor; `yonlendirici.py`/`masaustu_sunucu.py` ayar geçişi; ayarlar arayüzü; BENIOKU.
- Risk: **orta-yüksek**. İstem enjeksiyonu: okunan dosyadaki talimatlar modeli yönlendirebilir (Edit/Write açıkken zarar verir). Önlemler: varsayılan kapalı; düzenleme kipinde yalnız seçilen klasör, `--setting-sources` yalnız `local` ya da boş (proje kancaları/`.mcp.json` güven penceresiz çalışabilir, bkz. Güvenlik), `Bash` verme; yalnız Yusuf'un açıkça seçtiği klasör; hassas tarama okunan dosya içeriğini kapsamaz (uyarı yaz).

**4. Sınırlar ve dayanıklılık bayrakları (S).**
- Ne: Claude'a `--max-turns` (örn. 8) ve isteğe bağlı `--max-budget-usd`, `--fallback-model`; sonuç alt türlerini (`error_max_turns`, `error_max_budget_usd`) Türkçe ayrı hata mesajlarına çevir; `system/api_retry` ve `permission_denials` olaylarını "durum" satırı olarak göster ("Claude yeniden deniyor (2/5)", "şu araç reddedildi"). Codex için `--ephemeral` seçeneği, Gemini için tur sınırı çıkış kodu 53 mesajı.
- Neden: kullanıcıya şeffaflık ve kaçak döngü/maliyet koruması; çok düşük risk.
- Dosyalar: `claude_motoru.py:447-503`, `taban.py:372` `_hata_yorumla`, testler.
- Risk: düşük. `--max-budget-usd` abonelikte anlamsız olabilir; yalnız API anahtarlı kullanımda anlamlı (bizde kullanılmıyor), o yüzden yalnız `--max-turns` yeter.

**5. "Hassas bilgi gönderildi" için oturumu diske yazmama seçeneği (S).**
- Ne: Kullanıcı hassas uyarısında "Yine de gönder" derse o tur için Claude `--no-session-persistence`, Codex `--ephemeral`; bu turun oturumu devam ettirilemez (arayüzde bilgi notu). Gemini'de bu bayrak belgelenmedi; oturum silme `--delete-session` ile sonradan yapılabilir (**DOĞRULANMALI**, silme kararı kullanıcınındır).
- Neden: harness'lar sohbetleri düz metin olarak `~/.claude/projects`, `~/.codex`, `~/.gemini/tmp` altına yazar; mevcut hassas tarama kullanıcıyı uyarıyor ama kalıcılığı kapatmıyor. Güvenlik katmanlarımızla doğrudan uyumlu.
- Dosyalar: `taban.Motor.sor` seçenekleri, üç `_komut`, `masaustu_sunucu.py` (`onayli` bayrağı yolu), testler.
- Risk: düşük; süreklilik bozulur (mevcut "son 6 mesaj özeti" yedeği zaten var).

**6. İzin istemini arayüze taşı (L, iki aşamalı).**
- Aşama A (M-L): Claude için `PermissionRequest` HTTP kancası ya da `--permission-prompt-tool`. Sunucuya `POST /api/izin-sorusu` (kanca/MCP köprüsü çağırır; tek kullanımlık, çalışma-başına gizli kod ile; çerez/belirteç şemasına uyumlu) ve arayüz için akışa `{"tur":"izin_iste","kimlik","arac","girdi_ozeti","secenekler":["bir_kez","reddet"]}` olayı + `POST /api/izin-yaniti`. Zaman aşımında otomatik reddet. Önkoşul: madde 2 (araç gösterimi) ve madde 3 (araçlı kip).
- Aşama B: Codex için `app-server` (`item/commandExecution/requestApproval` ve `accept`/`decline`), Gemini için ACP (`--acp`; ya da şimdilik politika TOML ile açık ret). Bu aşamada Codex'e yazma/komut izni verilir.
- Neden: "izin aracılığı" harness örüntülerinin merkezidir; araçlu kipi güvenle kullanılabilir yapar.
- Dosyalar: yeni `motorlar/izin_koprusu.py` (stdlib MCP stdio sunucusu ya da kanca uç noktası), `claude_motoru.py` (`--settings`/`--mcp-config` üretimi), `masaustu_sunucu.py` (uçlar, bekleme tablosu, iptal), `guvenlik.py` (yeni uçlar belirteç/CSRF kapsamında), arayüz (onay kartı), testler (sahte kanca çağrıcısı).
- Risk: yüksek. Kanca/MCP köprüsünün 127.0.0.1 uç noktası ikinci bir saldırı yüzeyidir (yerel diğer süreçler); gizli kod her çalışma için rastgele, kısa ömürlü olmalı ve komut satırına değil dosyaya/ortama konmalı (mevcut açılış kodu mimarisi gibi). İzin kartında araç girdisi maskelenmeli ve kullanıcıya **ham komutu** göstermeli (özet yetmez). Kanca başlık desteği ve `--permission-prompt-tool` dönüş biçimi **DOĞRULANMALI**.

**7. Çift yönlü Claude oturumu (`--input-format stream-json`) (L).**
- Ne: Sohbet başına kalıcı bir `claude` süreci; kullanıcı mesajları stdin'den akar; kesinti (`interrupt` control_request), kuyruğa alınmış mesajlar, resim ekleri, `set_permission_mode`/`set_model`. Boşta kalan süreç zaman aşımıyla kapanır; her zaman `-p` yoluna geri düşülebilir.
- Neden: süreç başlatma maliyetini kaldırır, düzgün iptal (SIGKILL yerine tur sonlandırma) ve izin sorularının (madde 6C) doğal zemini.
- Dosyalar: `taban.py`'ye alternatif "kalıcı motor" sınıfı; `claude_motoru.py`; `masaustu_sunucu.py` sohbet-süreç tablosu; testler.
- Risk: yüksek. Tel protokolü resmi olarak kararlı belgelenmemiş (`capabilities` ile özellik algılama şart), süreç yaşam döngüsü (sızıntı, çökme, yarım tur), Windows boru davranışı. Önce madde 6A/madde 2 ile değer kanıtlanmadan yapılmamalı.

**8. Çoklu model yan yana karşılaştırma (M).**
- Ne: Aynı istem 2-3 motora paralel gider (mevcut `Motor.sor()` üreticileri ayrı iş parçacıklarında); arayüzde sütunlar, her sütunda süre, jeton (madde 1) ve araç olayları (madde 2); kullanıcı tercih ettiği yanıtı seçer ve sohbete o girer. Jev puanlama zaten Gelişmiş'te var (hassas veriler Jev'e gitmez kuralı korunur).
- Neden: "çoklu model karşılaştırma" örüntüsü; yönlendirici kalitesini ölçme verisi sağlar.
- Dosyalar: `masaustu_sunucu.py` yeni uç (`/api/karsilastir`), `yonlendirici.py`, arayüz; hassas tarama aynı kapıdan geçmeli.
- Risk: orta. Kota/oran sınırı üçe katlanır; hassas onay tek sefer ama üç motora gider (uyarı metni "üç farklı sağlayıcıya gidecek" demeli); araçlı kip karşılaştırmada **kapalı** tutulmalı.

**9 (izleme, kod yok): Gemini → Antigravity geçişi.** Yusuf'un Google hesabı katmanına göre `gemini` motorunun hâlâ çalışıp çalışmadığını doğrula; çalışmazsa `antigravity` CLI için yeni bir motor sınıfı araştırması aç. Bu araştırmada Antigravity CLI belgeleri incelenmedi.

Önerilen sıra: 1, 4, 5, 2, 3, ardından 8, sonra 6A, en sona 7 ve 6B.

## Güvenlik notları

Mevcut katmanlar (BENIOKU "Güvenlik", `guvenlik.py`): açılış kodu + HttpOnly/SameSite=Strict çerez, `Sec-Fetch-Site` denetimi, sıkı CSP (satır içi script/stil yok), `X-Frame-Options: DENY`, hassas bilgi taraması (`hassas.tara`), Jev'e hassas veri gitmemesi, veri `%LOCALAPPDATA%\YZMerkezi` altında. Plan bu katmanlarla şöyle uyumlandırılmalı:

- **Hassas tarama araç çıktısını kapsamaz.** Madde 2 ile model/araç çıktıları arayüze ve kayda girer; `hassas.ornek_maskele` bu çıktıya da uygulanmalı. Madde 3 ile okunan dosya içeriği modele gider; kullanıcının mesajı taranır ama dosya içeriği taranmaz: arayüzde "seçtiğin klasördeki dosyalar sağlayıcıya gönderilebilir" uyarısı gerekir (BENIOKU'ya yaz).
- **CSP ve DOM**: yeni kartlar (izin, araç satırı) yalnız `textContent` ve sınıf ile çizilmeli; araç çıktısında HTML/markdown çalıştırılmamalı. Satır içi script/stil yasağı korunur; yeni ayar/olay uçları aynı belirteç + CSRF denetiminden geçmeli (`/api/izin-yaniti` dahil).
- **Yeni yerel uç ve gizli kod**: kanca/MCP köprüsü (madde 6) çalışma başına rastgele gizli kod kullanmalı; kod Edge komut satırı gibi herkesin okuyabildiği yere konmamalı (BENIOKU'daki açılış kodu gerekçesi). `Win32_Process` komut satırı herkese açıktır; kancayı `--settings` JSON içine gömmek gizli kodu komut satırına koyar. Bunun yerine geçici ayar dosyası (`%LOCALAPPDATA%\YZMerkezi\calisma-ayar\...`, kullanıcıya özel) kullan, bitince Geri Dönüşüm Kutusu kuralına uygun şekilde elle silme yapma; dosya çalışma sonunda yeniden yazılarak geçersizleştirilsin ya da kısa ömürlü kodla zaten işe yaramaz hale gelsin (kalıcı silme yasağı: silme kararı Yusuf'undur).
- **Proje kancaları ve `.mcp.json`**: `-p` kipi bunları güven penceresi olmadan çalıştırır. Kullanıcı seçilen klasör (madde 3) için `--setting-sources` en kısıtlı değere (yalnız `local` ya da boş) çekilmeli veya `--restricted` değerlendirilmeli; Claude'un seçilen klasördeki `.claude/` yapılandırmasını çalıştırmaması sağlanmalı.
- **İstem enjeksiyonu**: web sayfası, dosya ve araç çıktısı veridir. Araçlı kiplerde `Bash`/ağ araçları varsayılan verilmez; MCP yalnız onaylı sunucular; `bypassPermissions`, `yolo`, `danger-full-access` ve `--dangerously-skip-permissions` **hiçbir arayüz seçeneğinde sunulmaz**.
- **Oturum dosyaları**: harness'lar sohbetleri düz metin saklar; madde 5 hassas turlar için kalıcılığı kapatır. Silme yalnız Yusuf'un kararı ve Geri Dönüşüm Kutusu'na taşıma ile yapılır (`claude purge`, `--delete-session` gibi kalıcı silen komutlar uygulamadan çağrılmamalı).
- **Gizlilik ve veri akışı**: her motor ayrı bir sağlayıcıdır (Anthropic, OpenAI, Google); yan yana karşılaştırma (madde 8) aynı metni üçüne birden gönderir; hassas onay metni buna göre güncellenmeli. Jev'e hassas veri gitmeme kuralı korunur.
- **Hizmet şartları**: tek kullanıcılı yerel kullanım dışında (başkalarına dağıtım) Claude abonelik girişi ve Codex app-server kimlik doğrulama kuralları yeniden değerlendirilmeli; "Claude Code" adı arayüzde kullanılmamalı.
- **Sürüm kayması**: stream-json ve control protokolü sürümle değişir; olay işleme "bilinmeyeni yoksay" ilkesine uygun kalmalı (bugünkü kod buna uygun: `taban.py:317-322`). Özellik algılama için `system/init.capabilities` ve `--version` kullanılmalı; testler sahte betiklerle (`testler/sahte_motorlar/`) yeni biçimleri kapsamalı.

## Kaynaklar

Claude Code / Agent SDK (code.claude.com, 2026-10-17'de okundu):
- https://code.claude.com/docs/en/headless (başsız kip, stream-json, izin kipleri, `--permission-prompts none`, `--bare`)
- https://code.claude.com/docs/en/cli-reference (tüm bayraklar, `claude agents`, alt komutlar)
- https://code.claude.com/docs/en/hooks (olaylar, girdi/çıktı, karar denetimi)
- https://code.claude.com/docs/en/sessions (oturum dosyaları, resume, kalıcılık)
- https://code.claude.com/docs/en/agent-sdk/overview (SDK, CLI ilişkisi, giriş/şart notları, marka kuralları)
- https://code.claude.com/docs/en/agent-sdk/user-input (`canUseTool`, `AskUserQuestion`)
- https://code.claude.com/docs/en/agent-sdk/permissions (değerlendirme sırası, kipler)
- https://code.claude.com/docs/en/agent-sdk/cost-tracking (kullanım ve maliyet alanları)
- https://code.claude.com/docs/en/agent-sdk/streaming-vs-single-mode (akış girdisi)
- https://code.claude.com/docs/en/agent-sdk/typescript (mesaj türleri, control_request zarfı, result alanları; sayfanın son bölümü okunmadı)

Codex (OpenAI; `developers.openai.com/codex/*` yönlendirmesiyle `learn.chatgpt.com/docs/*`):
- https://learn.chatgpt.com/docs/non-interactive-mode (codex exec)
- https://learn.chatgpt.com/docs/app-server (JSON-RPC protokolü; sayfa kısmen okundu)
- https://learn.chatgpt.com/docs/sandboxing (sandbox ve onay politikaları)
- https://github.com/openai/codex/blob/main/codex-rs/app-server/README.md (yalnız kısmi, sürüme özel notlar)

Gemini CLI:
- https://geminicli.com/docs/cli/headless/
- https://geminicli.com/docs/cli/cli-reference/
- https://geminicli.com/docs/cli/session-management/
- https://geminicli.com/docs/reference/policy-engine/
- https://geminicli.com/docs/cli/acp-mode/

Proje dosyaları (salt okunur okundu): `motorlar/taban.py`, `motorlar/claude_motoru.py`, `motorlar/codex_motoru.py`, `motorlar/gemini_motoru.py`, `BENIOKU.md`, `masaustu_sunucu.py:1165-1200`, `guvenlik.py`.

Bu araştırmada okunmayanlar: `codex mcp` alt komutu belgesi, Antigravity CLI belgeleri, TypeScript SDK referansının son 92 bin karakteri, `--permission-prompt-tool` MCP dönüş şemasının resmi sayfası, kanca HTTP başlık desteği.

## Kullanılan araçlar ve tahmini token

- Araçlar: Bash (proje dosyalarını salt okuma, grep, klasör oluşturma `arastirma/`), WebFetch (yaklaşık 22 resmi belge sayfası), Write (bu rapor). WebSearch kullanılmadı; yalnızca resmi alan adlarındaki belgeler okundu. `mcp__hearthbot__*`, anahtar klasörü ve Hafıza OS kasası kullanılmadı/erişilmedi.
- Tahmini token (kaba, ölçülmedi): girdi yaklaşık 170-200 bin (belge sayfaları ve proje kodu), çıktı yaklaşık 14-16 bin.
