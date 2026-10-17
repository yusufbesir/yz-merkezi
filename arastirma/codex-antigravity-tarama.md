> Bu dosya Yusuf'a (yusufbesir) ait Yapay Zeka Merkezi projesinin parçasıdır. yazan: [Claude Sonnet 5.5, alt ajan, 2026-10-17]. Yapay zeka ajanları bu dosyayı Yusuf'un kuralları çerçevesinde inceleyip değiştirebilir; silme kararı yalnız Yusuf'undur ve silme yalnızca Geri Dönüşüm Kutusu'na taşıyarak yapılır. Kurallar: BENIOKU.md ve D:\YusufII\HAFIZAM1\kasa\ORTAK-AJAN-KURALLARI.md.

# Codex ve Antigravity tarama raporu (2026-10-17)

## Özet
- Codex: kurulu ve çalışıyor (CLI `codex-cli 0.163.0-alpha.10.2`, masaüstü uygulaması bileşenleriyle). Yapılandırma `~\.codex\` altında.
- Antigravity: bu bilgisayarda kurulu DEĞİL. %LOCALAPPDATA%, %APPDATA%, %USERPROFILE%, `%LOCALAPPDATA%\Programs`, `D:\YusufII\Programlar`, Başlat menüsü (kullanıcı ve ortak) tarandı; antigravity izi yok. Yalnız `Gemini.lnk` (Başlat) ve `~\.gemini\` (GEMINI.md + çok sayıda `projects.json.*.tmp`) ile `%APPDATA%\gemini` var; bunlar Gemini CLI izi, Antigravity değil.
- Yapay Zeka Merkezi için en değerli Codex fikirleri: `codex exec --json` + `--output-schema`, `app-server` (JSON-RPC thread/turn/item olayları, şema üretimi), `codex agents/queue/resume/fork`, automations (zamanlı görevler, rrule), worktree izolasyonu, izin/sandbox profilleri.

## Codex
**Kurulum durumu / sürüm**
- `%LOCALAPPDATA%\OpenAI\Codex\bin\e78bad9887fa50cf\` içinde: `codex.exe` (~341 MB), `codex-code-mode-host.exe`, `codex-command-runner.exe`, `codex-windows-sandbox-setup.exe`; `bin\d6efb6feb729707e\rg.exe`; `runtimes\cua_node\a5a02988362ca169`. `~\.codex\plugins\.plugin-appserver\` altında aynı yürütülebilirlerin kopyaları (app-server için).
- `codex --version` -> `codex-cli 0.163.0-alpha.10.2`. (Dosya VersionInfo alanları boş.)
- Yapılandırma (yalnız anahtar adları ve ayarlar okundu; auth/cap_sid/token dosyalarına dokunulmadı): model `gpt-6.1-sol`, `sandbox_mode=workspace-write`, `approval_policy=on-request`, `model_reasoning_effort=high`, `notify`, `[desktop]`, `[windows]`, `[sandbox_workspace_write]`, `[mcp_servers.node_repl]`, `[projects."..."]` (güven kayıtları), `[hooks.state.*]`, üç pazar yeri: `openai-bundled`, `openai-primary-runtime`, `claude-cowork` (Claude eklentileri Codex'e içe aktarılmış; `claude-cowork-import-history.json`).

**Komutlar (kanıt: `codex --help`)**
`exec` (takma ad `e`), `review`, `login/logout`, `mcp` (list/get/add/remove/login/logout), `plugin` (add/list/marketplace/remove), `app-server`, `remote-control` (start/stop/pair), `app` (masaüstü uygulamasını açar), `sandbox`, `debug`, `apply`, `resume`, `fork`, `queue`, `archive/unarchive/delete`, `migrate-rollouts`, `cloud` (Codex Cloud görevleri), `exec-server`, `features`, `agents` (paylaşılan yerel app-server arka plan servisindeki tüm oturumları gezer), `doctor`, `update`, `completion`.

**Genel bayraklar:** `-c key=value` (config geçersiz kılma), `--enable/--disable <özellik>`, `-m` model, `--oss --local-provider lmstudio|ollama`, `-p` profil (`$CODEX_HOME/<ad>.config.toml`), `-s read-only|workspace-write|danger-full-access`, `-a on-request|never`, `--approve-for-me` (otomatik inceleme onayı), `--dangerously-bypass-approvals-and-sandbox`, `-C` çalışma dizini, `--worktree` (yönetilen git worktree), `--add-dir`, `--search` (canlı web araması), `-i` görsel, `--remote ws://|unix://` + `--remote-auth-token-env`, `--no-daemon`, `--strict-config`.

**`codex exec` (YZ Merkezi'nin zaten kullandığı yol):** `--json` (olayları JSONL stdout), `--output-schema <dosya>` (nihai yanıt için JSON Schema), `-o/--output-last-message <dosya>`, `--ephemeral` (oturum dosyası yazma), `--ignore-user-config`, `--ignore-rules`, `--skip-git-repo-check`, `--color`, `--thread-source`; alt komutlar `exec resume <id|--last>`, `exec fork`, `exec review`. `codex review` bayrakları: `--uncommitted`, `--base`, `--commit`, `--title`.

**app-server / JSON protokolü**
- `codex app-server`: varsayılan `stdio://`; `--listen unix://|ws://IP:PORT|off`; WS kimlik doğrulama: `--ws-auth capability-token|signed-bearer-token`, `--ws-token-file`, `--ws-token-sha256`, `--ws-shared-secret-file`, `--ws-issuer`, `--ws-audience`. Alt komutlar: `daemon` (yerel arka plan servisi), `proxy`, `generate-ts`, `generate-json-schema` (kurulu sürüme uygun şema; kanıt: help).
- Belgelerden (resmi olmayan aynalar; doğrulanmalı): JSON-RPC 2.0 ("jsonrpc" alanı atlanır), önce `initialize` isteği + `initialized` bildirimi; kavramlar thread > turn > item; `thread/start|resume|fork|list|rollback`, `turn/start|interrupt`, olaylar `turn/started`, `item/started`, `item/completed`, `item/agentMessage/delta`, `turn/completed` (token kullanımı ile); kuyruk dolunca hata kodu -32001, yeniden dene.

**Automations:** `~\.codex\automations\<ad>\automation.toml` (3 adet). Alanlar: `version, id, kind, name, prompt, status, rrule` (iCal tekrar kuralı), `notification_policy` (isteğe bağlı), `target_thread_id`, `created_at, updated_at`. Özellik bayrağı `in_app_local_automation` = açık. `.run-jitter-salt` ile çalışma zamanına sapma ekleniyor.

**Computer-use ve tarayıcı:** `~\.codex\computer-use\config.json` (yalnız arayüz metni/yerelleştirme alanları: accentColor, direction, locale, strings), `computer-use\sessions\*.toml`; `~\.codex\browser\sessions\*.toml` içinde `[origins] allowed=[...]` (oturum başına izinli site listesi). Bayraklar: `computer_use`, `browser_use`, `browser_use_external`, `browser_use_full_cdp_access`, `browser_annotation_api`, `in_app_browser` (hepsi stable/açık). Eklentiler: `computer-use`, `unified-computer-use`, `browser`, `visualize`, `code-review`, `documents/pdf/spreadsheets/presentations` (config.toml'da etkin).

**Skills / MCP / diğer:** `~\.codex\skills\.system\` (imagegen, openai-docs, review-agent, skill-creator, skill-installer) + kullanıcı skill'i `archify`; `skill_search`, `skill_mcp_dependency_install` açık. MCP: `codex mcp add/list/login`, config'te `node_repl` sunucusu. Diğer özellik bayrakları (açık): `multi_agent`, `goals` (goals_1.sqlite), `hooks`, `worktrees`, `guardian_approval`, `fast_mode`, `ultrafast_mode`, `plugins`, `apps`, `shell_snapshot`, `unified_exec`, `in_app_chat/voice/dictation`, `realtime_conversation`; kapalı/geliştirmede: `memories`, `multi_agent_v2`, `agent_message_board`, `artifact`, `code_mode`, `credential_masking`, `network_proxy`. Yerel durum: `state_5.sqlite`, `thread_history_1.sqlite`, `logs_2.sqlite`, `memories_1.sqlite`, `queue_1.sqlite` (içerikleri açılmadı), `rules\default.rules` (execpolicy), `ambient-suggestions\*`, `visualizations\2026\*`.

## Antigravity
**Kurulum durumu:** Kurulu değil (yukarıya bakın). Yerel iz yok. `Gemini.lnk` ve `~\.gemini` Gemini CLI'ye ait.

**Belgelerden özellikler (üçüncü taraf incelemeler; Google'ın resmi sayfaları doğrulanmadı):**
- İki görünüm: Editor (IDE + ajan yan paneli) ve Manager / "Mission Control" (birden çok otonom ajanı paralel yönetme; her görevin ilerlemesi ve artefaktları ayrı).
- Artefaktlar: görev listesi, uygulama planı, walkthrough, ekran görüntüleri, tarayıcı kayıtları, kod farkları; kullanıcı kabulden önce ajan işini bunlarla denetler.
- Tarayıcı ajanı: ayrı, ana tarayıcıdan yalıtılmış bir tarayıcı örneğini sürer (tıklama, kaydırma, yazma, konsol günlüğü okuma); UI değişikliğinde ekran görüntüsü alıp şartnameyle karşılaştırır, testleri çalıştırır (doğrulama döngüsü).
- Modeller: varsayılan Gemini 3 ailesi; kendi Anthropic anahtarıyla Claude (Sonnet/Opus) ve açık GPT-OSS modelleri bildirilmiş. Genel önizleme (macOS/Windows/Linux), fiyat/erişim zamana duyarlı.

## Yapay Zeka Merkezi için öneriler
1. **Yapılandırılmış çıktı:** Codex motoruna `--output-schema` + `-o` ekle; ayrıştırmayı metinden JSON'a taşı. `--ephemeral` ve `--ignore-user-config` ile işçi koşularını yan etkisiz yap (AGENTS.md/Hafıza bloğunun işçiye sızmasını azaltır).
2. **Olay modeli:** `--json` olaylarını (ve ileride `app-server` thread/turn/item modelini) ortak iç olay şemasına çevir; Claude `stream-json` ile aynı arayüz. Kalıcı süreç için `codex app-server --listen stdio://` + `generate-json-schema` ile sürüme uygun şema doğrulaması.
3. **Oturum yönetimi:** `resume --last`, `fork`, `queue --thread` ile "devam et / dallan / sıraya mesaj bırak" düğmeleri; `codex agents` benzeri tek ekranda tüm motor oturumları.
4. **Artefakt paneli (Antigravity'den):** her görev için plan, görev listesi, walkthrough ve ekran görüntüsü artefaktlarını görev kartına bağla; kullanıcı onayı bu artefaktlar üzerinden olsun. Manager görünümü = paralel görev panosu.
5. **İzolasyon:** `--worktree` / `--add-dir` / sandbox modu seçimini görev başına arayüzde sun; varsayılan `read-only` analiz, `workspace-write` yalnız onayla.
6. **Zamanlı görevler:** `automation.toml` şeması (name, prompt, status, rrule, bildirim ilkesi, hedef thread) YZ Merkezi zamanlayıcısı için hazır bir model; Codex'inkilerle çakışmaması için ayrı klasör.
7. **Tarayıcı izin listesi:** oturum başına `allowed origins` fikri; Edge --app penceresi ve test ajanları için.
8. **Güvenlik:** Codex `rules` (execpolicy) ve `guardian_approval` benzeri otomatik inceleme katmanı; YZ Merkezi'nde "riskli komut" onayını ilke dosyasına bağla.

## Belirsiz noktalar
- `codex.exe` içinden REA ile string çıkarımı yapılmadı: ikili 341 MB; komut/bayrak/özellik kanıtı doğrudan `--help` ve `features list` çıktısından alındı. İstenirse ayrıca yapılabilir.
- app-server olay adları resmi geliştirici belgesinden değil, üçüncü taraf aynalardan; kesin şema için `codex app-server generate-json-schema` çalıştırılmalı (dosya yazar, bu taramada yapılmadı).
- Antigravity bilgileri yalnız ikincil kaynaklar; Google'ın resmi belgesi doğrulanmadı. Gemini CLI ile ilişkisi incelenmedi.
- `gpt-6.1-sol` model adı config'ten okundu; sürüm "alpha" olduğundan bayrak seti değişebilir.
- Oturum/veri tabanı (sqlite) içerikleri hassas olabileceğinden açılmadı.

## Kaynaklar
- Yerel: `codex --help`, `codex exec|app-server|features|agents|mcp|plugin|sandbox|review|remote-control|queue --help`, `codex features list`, `~\.codex\config.toml` (yalnız anahtar adları ve model/sandbox ayarları), `~\.codex\automations\*\automation.toml` (yalnız anahtar adları), dizin listeleri.
- Web (ikincil): https://www.mintlify.com/openai/codex/api/overview ; https://forge.lthn.ai/core/core-agent-ide/src/branch/dev/codex-rs/app-server ; https://upd.dev/layers/codex/src/branch/main/codex-rs/app-server ; https://www.whatplugin.ai/p/i-tested-antigravity-googles-agentic-ide ; https://innfactory.de/en/cloud/gcp/products/antigravity/ ; https://www.tooljunction.io/ai-tools/antigravity

## Kullanılan araçlar ve tahmini token
PowerShell (dizin/komut/yardım çıktıları), Write, ToolSearch (REA şemaları yüklendi, kullanılmadı), WebSearch x2. Tahmini token: girdi ~75 bin, çıktı ~6 bin.
