> Bu dosya Yusuf'a (yusufbesir) ait Yapay Zeka Merkezi projesinin parçasıdır. yazan: [Claude Opus 5.5, alt ajan, 2026-10-17]. Yapay zeka ajanları bu dosyayı Yusuf'un kuralları çerçevesinde inceleyip değiştirebilir; silme kararı yalnız Yusuf'undur ve silme yalnızca Geri Dönüşüm Kutusu'na taşıyarak yapılır. Kurallar: BENIOKU.md ve D:\YusufII\HAFIZAM1\kasa\ORTAK-AJAN-KURALLARI.md.

# Claude masaüstü uygulaması (Windows, 2.42304.0) salt okunur tarama raporu

## Özet

- Claude masaüstü, Electron 44.7.2 üzerinde çalışan bir "kabuk + yerel ajan sunucusu". Paket adı `@ant/desktop` 2.42304.0. Arayüz (renderer), claude.ai web uygulamasının yerel kopyası (`resources/ion-dist`, 202 MB). Bu kopya `app://` protokolüyle yükleniyor. Yerel yetenekler (oturumlar, dosya, git, terminal, önizleme, MCP) ana süreçte duruyor ve arayüze IPC ile açılıyor.
- **Harness'in çekirdeği:** Uygulama Claude Code CLI'ını doğrudan `-p` ile çağırmıyor. Gömülü **Claude Agent SDK 0.3.299** (`query()`) üzerinden çağırıyor. SDK, CLI'ı her zaman şu bayraklarla başlatıyor: `--output-format stream-json --verbose --input-format stream-json`. Sonra stdin/stdout üzerinde **çift yönlü JSON satır protokolüyle** konuşuyor: `user` mesajları, `control_request`, `control_response` ve `control_cancel_request`.
- İzinler CLI'dan masaüstüne **`control_request{subtype:"can_use_tool"}`** ile geliyor (`--permission-prompt-tool=stdio`). Masaüstü bunu arayüzde kart olarak gösteriyor (`onToolPermissionRequest` / `respondToToolPermission`). Hook'lar da aynı kanaldan **`hook_callback`** ile, uygulama içi MCP araçları ise **`mcp_message`** ile taşınıyor.
- Uygulama CLI'ın **kendi sabitlenmiş sürümünü** indiriyor. Kaynak `downloads.claude.ai/claude-code-releases`, hedef `%APPDATA%\Claude\claude-code\2.1.299\`. İndirmede sha256 doğrulanıyor ve `sdkCompat.harnessSchema:1` ile `testedWrapperVersions` uyumluluk denetimi yapılıyor. "Harness" kelimesi kodda tam olarak bu sürüm/uyum sözleşmesini ve `harnessCwd` çalışma klasörü kavramını karşılıyor.
- Özellik yüzeyi çok geniş. IPC arayüzlerinde en büyük üç grup şöyle: `LocalSessions` (Code sekmesi, 338 yöntem), `LocalAgentModeSessions` (Cowork, 126 yöntem) ve `Launch` (tarayıcı/önizleme paneli, 108 yöntem). Ayrıca git/PR, SSH uzak oturum, worktree, terminal (node-pty), zamanlanmış görevler, eklenti pazarı, MCP/DXT uzantıları, uzaktan kontrol ve bilgisayar kullanımı (computer use) var.
- Yapay Zeka Merkezi'nin bugünkü Claude motoru (`motorlar/claude_motoru.py`) her turda yeni bir `claude -p` başlatıyor ve araçları kapatıyor (`--tools ""`). En büyük kazanç **kalıcı, çift yönlü stream-json oturumuna** geçmekten gelir: `--input-format stream-json` ve `--permission-prompt-tool stdio`, izin istekleri de arayüzde kart olarak gösterilir. Bu, masaüstünün yaptığının birebir Python karşılığıdır.

## Kurulum ve mimari

| Konu | Bulgu | Kanıt |
|---|---|---|
| Kurulum biçimi | MSIX (WindowsApps), paket `Claude_2.42304.0.0_x64__pzs8sxrjxfjjc` | klasör yolu; ana süreçte `msix_required`, `msix_deploy_shape_*` dizgileri |
| Electron | 44.7.2 | `app\version` dosyası |
| Ana giriş | `.vite/build/index.pre.js` (930 KB). Asıl ana süreç mantığı `index.chunk-lzaSYO3Q.js` (7 MB). Toplam 377 Vite parçası. | `package.json` `"main"` |
| Fuses | RunAsNode **kapalı**, NODE_OPTIONS **kapalı**, `--inspect` **kapalı**, CookieEncryption **açık**, EmbeddedAsarIntegrityValidation **açık**, OnlyLoadAppFromAsar **açık**, GrantFileProtocolExtraPrivileges açık, WasmTrapHandlers açık | REA `inspect_electron_fuses`, claude.exe ofset 198745352 |
| asar | `resources/app.asar` (49 MB). Yalnız scratchpad'e çıkarıldı. Unpacked içerik: `node-pty`, `@ant/claude-native` | `app.asar.unpacked/node_modules` |
| Renderer | `resources/ion-dist/index.html` bir claude.ai SPA yapısı (`data-entry-document="app"`). Ana süreç bunu `app://` protokolüyle sunuyor. | `index.chunk-lzaSYO3Q.js`: `k8r(n.default.join(uIa(),"ion-dist"), ...)` ve "Failed to install app:// protocol" |
| Preload / köprü | `mainView.js` şunları `contextBridge.exposeInMainWorld` ile açıyor: `claudeAppBindings`, `claudeAppSettings`, `desktopBootFeatures`, `desktopManagedConfig`, `electronWindowControl`... IPC kanal biçimi: `$eipc_message$_<uuid>_$_claude.web_$_<Arayüz>_$_<yöntem>` | `mainView.js` |
| Yardımcı süreçler / işçiler | `pty-host/ptyHostWorker.js` (terminal), `mcp-runtime/{nodeHost,directMcpHost}.js` (MCP sunucu barındırma), `file-index-worker`, `transcript-search-worker`, `shell-path-worker`, `heavy-work-worker`, `msal-broker-worker` | `.vite/build/` |
| Ek ikili dosyalar | `cowork-svc.exe` (Cowork VM servisi), `smol-bin.x64.vhdx` (VM diski), `claude-ssh-{broker,proxy,askpass}.exe`, `chrome-native-host.exe` + `claude-browser-shim.js` (Chrome eklentisi köprüsü) | `resources/` |
| Önemli bağımlılıklar | `@anthropic-ai/claude-agent-sdk` 0.3.299, `@modelcontextprotocol/sdk`, `@anthropic-ai/mcpb` 2.1.2 (DXT/MCPB uzantıları), `node-pty`, `@xterm/headless`, `playwright-core` 1.57, `ssh2`, `electron-store`, `@sentry/electron` | `package.json` |
| Güncelleme | Electron `autoUpdater` + `setFeedURL({url, serverType:"json"})`. Kademeli dağıtım ve geri alma desteği var (`[updater] ... Rollback unstage complete`). Çalışan oturum varsa "boşta yeniden başlat" seçeneği sunuluyor (`AutoUpdater.restartToUpdateWhenIdle`, `getRunningLocalSessionCount`). | `index.pre.js` / ana parça |
| CLI dağıtımı | Gömülü manifest: `baseUrl:"https://downloads.claude.ai/claude-code-releases"`, platform başına `claude.exe.zst` + sha256 + boyut, `sdkCompat{testedWrapperVersions[], harnessSchema:1}`. Uyumsuzluk nedenleri: `manifest_version_mismatch`, `unsupported_harness_schema`, `wrapper_version_unknown` | ana parça (`harnessSchema` çevresi) |
| Kullanıcı verisi (yalnız yapı) | `%APPDATA%\Claude\`: `claude-code\2.1.295, 2.1.299` (indirilmiş CLI'lar), `claude-code-sessions\<hesap>\<org>\local_<uuid>.json`, `scheduled-tasks.json`, `archived-sessions.idx`, `claude-code-vm\`, `vm_bundles\`, `local-agent-mode-sessions\` (Cowork), `git-worktrees.json`, `git-shadow\`, `scratch-workspaces\`, `ccd-session-presets.json`, `claude_desktop_config.json`, `remote-control-state.json`, `logs\` | dizin listesi (içerik okunmadı; token içeren dosyalar açılmadı) |

**Oturum meta dosyasının alanları** (`local_<uuid>.json`, yalnız anahtar adları): `sessionId`, `cliSessionId`, `cwd`, `originCwd`, `model`, `effort`, `permissionMode`, `chromePermissionMode`, `sessionPermissionUpdates`, `alwaysAllowedReasons`, `title`, `titleSource`, `completedTurns`, `lastAssistantUuid`, `isArchived`, `postTurnSummary{needs_action,status_category,status_detail}`, `toolSurfaceSnapshot{cliVersion,appVersion,...}`, `promptAppendSnapshot`, `remoteControlSpawn`, `remoteMcpServersConfig`. Bu yapıdan çıkan sonuç: masaüstü kendi oturum kaydını tutuyor (UI durumu, izin kararları, özet). Asıl konuşma ise CLI'ın `~/.claude/projects/<proje>/<cliSessionId>.jsonl` dosyasında duruyor (kodda `"projects"` + `${cliSessionId}.jsonl` birleşimi var).

**`ccd-session-presets.json`**: `byAccount.<hesap>.presets[]{id,name,createdAt,lastUsedAt,settings{modelId,effort},target{kind,cwd}}`.
**`claude_desktop_config.json`**: `coworkUserFilesPath` ve `preferences{...}`. Tercih örnekleri: `bypassPermissionsGateByAccount`, `ccAutoArchiveInactiveDays`, `ccAutoArchiveOnPrClose`, `ccdScheduledTasksEnabled`, `coworkWebSearchEnabled`, `remoteControlPinnedFolders`, `sidebarMode`.

## Özellik haritası

Kanıt, `mainView.js` içindeki IPC arayüz/yöntem adlarına ve ana süreç dizgilerine dayanıyor. Dosyalar küçültülmüş (tek satır) olduğu için satır numarası yerine dizgi verildi.

| Alan | Ne yapıyor | Kanıt (IPC arayüzü / dizgi) |
|---|---|---|
| **Code sekmesi (CCD = Claude Code Desktop)** | Yerel Claude Code oturumlarını başlatma, mesaj gönderme, durdurma, kesme (interrupt), çatallama (fork), geri sarma (rewind/rewindFiles/undoRewind), arşivleme, yeniden adlandırma; model, effort, hızlı mod ve izin modu değiştirme; kuyruktaki mesajları yönetme (`cancelQueuedMessage`, `promoteQueuedMessage`, `reorderQueuedMessage`); yan sohbet (`startSideChat`, `startBtwChild`); bağlam kullanımı (`getContextUsage`); transkripti sayfalı okuma (`getTranscriptPage`, `getTranscriptTail`) | `LocalSessions_$_start/sendMessage/interrupt/forkSession/rewind/setPermissionMode/...` (338 yöntem) |
| CLI oturumu içe aktarma | Terminalde açılmış `claude` oturumlarını listeleme ve devam ettirme | `listCliSessions`, `listResumableCliSessions`, `resumeCliSession`, `importAllCliSessions`, `previewCliResume`, `HistoryImport_*`, `CliSessionImport_*` |
| İzin akışı | CLI'dan gelen araç izni arayüzde kartla gösteriliyor ve cevap CLI'a iletiliyor. Klasöre güven ("trust") ayrıca soruluyor. | `onToolPermissionRequest`, `respondToToolPermission`, `checkTrust`, `saveTrust`, `answerPendingCwdTrust`; sınıfta `pendingPermissions` haritası |
| İzin modları | `default`, `acceptEdits`, `plan`, `bypassPermissions`, `dontAsk`, `auto` | ana parça: `e.Default="default",e.AcceptEdits="acceptEdits",e.Plan="plan",e.Bypass="bypassPermissions",e.DontAsk="dontAsk",e.Auto="auto"` |
| Git / worktree | Oturum başına worktree (`git worktree add --no-checkout ... -b`, `.claude/worktrees`), dal değiştirme çakışma kontrolü, stash, WIP commit, diff, commit listesi, kalan worktree temizliği | `["worktree","add","--no-checkout",...]`, `["worktree","prune"]`, `getGitDiff`, `stashWorkingTree`, `discardKeptWorktree`, `checkBranchSwitchConflict` |
| GitHub PR | PR durumu, kontroller (checks), inceleme yorumları, birleştirme, otomatik birleştirme, taslak/hazır işaretleme, PR kapanınca otomatik arşiv | `getPrChecks`, `mergePr`, `enableAutoMerge`, `submitPrReview`, `armAutoFixOnNextPr`; uygulama içi MCP `ccd_pr` (`bind_pr`, `get_status`, `set_monitor`, `set_auto_merge`) |
| SSH / WSL / uzak | Uzak makinede Claude Code çalıştırma, SSH parola kuyruğu, uzak git, WSL dağıtımları | `getSSHConfigs`, `testSSHConnection`, `respondToSSHPassword`, `listWslDistros`, `claude-ssh-*.exe` |
| Terminal paneli | node-pty ile kabuk açma, yazma ve boyutlandırma | `startShellPty`, `writeShellPty`, `resizeShellPty`, `getTerminalShells`, `pty-host/ptyHostWorker.js` |
| Dosya paneli | Oturum klasörünü listeleme/okuma/yazma, dosya önizleme, dosya içinde arama, @-mention seçenekleri | `listSessionDirectory`, `readSessionFile`, `writeSessionFile`, `Resources_fetchMentionOptions`, `searchFileContents`, `FileSystem_*`, `file-index-worker` |
| Tarayıcı / önizleme paneli (Launch) | Geliştirme sunucusunu algılama (gerekirse ajanla: `detectServerCandidatesWithAgent`), önizleme sekmeleri, ekran görüntüsü, konsol günlükleri, öğe seçme (`toggleSelectionMode`, `elementSelected`), görüntü alanı, modelin gezinmesi (`navigatePreviewFromModel`), otomatik doğrulama | `Launch_*` (108 yöntem). Dev-server algılama ayrı bir tek atışlık `query()` ile yapılıyor: "Detect this project's dev server(s) and respond with the JSON block." |
| **Cowork (yerel ajan modu)** | Ayrı bir VM içinde (`cowork-svc.exe`, `smol-bin.x64.vhdx`, `ClaudeVM_startVM`) ya da "HostLoop" ile ana makinede çalışan ajan; klasör izinleri, salt okunur bağlama, çıktı klasörü, bellek, alanlar (Spaces), zamanlanmış görevler, Chrome araçları | `LocalAgentModeSessions_*` (126), `CoworkSpaces_*`, `CoworkMemory_*`, `CoworkScheduledTasks_*`, `ClaudeVM_*`; `[HostLoop] Starting Claude Code through the host CLI launcher`; `CLAUDE_CODE_ENTRYPOINT:"local-agent"` |
| Artifacts | Cowork artifact listesi, sürümleri, yıldızlama, PDF'e yazdırma; artifact kütüphaneleri (chart.js, gridjs, mermaid) yerelde | `CoworkArtifacts_*`, `resources/artifact-libs/`, `coworkArtifact.js` |
| MCP | Kullanıcı MCP yapılandırması, durum, OAuth, araç çağırma, kaynak okuma; oturum başına MCP sunucusu değiştirme; Node tabanlı MCP barındırma | `MCP_setMcpServerConfigs/getMcpServersConfigWithStatus`, `LocalSessions_mcpCallTool/mcpReconnect/setMcpServers/replaceEnabledMcpTools`, `mcp-runtime/` |
| Uygulama içi MCP sunucuları (CLI'a verilen araçlar) | Masaüstü, CLI oturumuna kendi araçlarını SDK MCP sunucusu olarak ekliyor: `ccd_session`, `ccd_view`, `ccd_window`, `ccd_host`, `ccd_directory`, `ccd_settings`, `ccd_config`, `ccd_pr`, `ccd_sidebar`, `ccd_session_mgmt` (`list_sessions`, `send_message`, `set_session_permission_mode`...) | `createSdkMcpServer({name:..., tools:...})`; "Session ... not found. Use list_sessions..." |
| Uzantılar / eklentiler | DXT/MCPB masaüstü uzantıları (imza denetimi), eklenti pazarı (marketplace), yerel skill'ler, gömülü skill'ler (docx, pdf, pptx, xlsx, frontend-design) | `Extensions_*`, `CustomPlugins_*`, `LocalPlugins_*`, `resources/bundled-skills/` |
| Zamanlanmış görevler | Code ve Cowork için cron benzeri görevler; uyanma zamanlayıcısı | `CCDScheduledTasks_*`, `WakeScheduler_*`, `scheduled-tasks.json`, `cronstrue` bağımlılığı |
| Uzaktan kontrol | Yerel oturumu buluttan/telefondan sürme; klasör sabitleme | `RemoteControlServing_*`, `toggleRemoteControl`, `teleportToCloud`, `remote-control-state.json` |
| Bilgisayar kullanımı | Ekran izni, canlı önizleme, kaydet-öğret | `ComputerUseTcc_*`, `computerUseTeach.js`, `@ant/computer-use-mcp` |
| Chrome entegrasyonu | Chrome eklentisi + native host; Chrome girişlerini önizlemeye aktarma | `ChromeExtension_*`, `chrome-native-host.exe`, `Launch_importChromeLogins` |
| Diğer | Hızlı giriş penceresi + global kısayol, masaüstü bildirimleri (eylem düğmeli), oturum açılır pencereleri (popout), komut paleti, depolama temizliği, Office eklentisi köprüsü, iOS Simulator paneli (macOS), "Buddy" BLE cihazı | `QuickEntry_*`, `GlobalShortcut_*`, `DesktopNotifications_showNotificationWithActions`, `SessionPopouts_*`, `MenuEvents_openCommandPalette`, `DeviceStorage_*`, `OfficeAddinFiles_*`, `Simulator_*`, `Buddy_*` |
| Tek atışlık yardımcı ajanlar | Başlık/stil üretimi, kullanım sorgusu (usage probe), dev-server algılama. Hepsi araçsız ve kalıcı oturumsuz `query()` çağrıları (`persistSession:false`, `allowedTools:[]`, `canUseTool: deny`). | `[StyleDrafter]`, `[UsageProbe]`, "usage probe has no tools" |

## Harness (ajan zemini) nasıl çalışıyor

### 1. Katmanlar

```
ion-dist (React arayüzü)
   │  ipcRenderer.invoke("$eipc_message$_..._$_claude.web_$_LocalSessions_$_sendMessage", ...)
   ▼
Ana süreç: LocalSessions yöneticisi (oturum kaydı, izin kuyruğu, git, pty, önizleme)
   │  @anthropic-ai/claude-agent-sdk  query({prompt: AsyncIterable, options})
   ▼
claude.exe (%APPDATA%\Claude\claude-code\2.1.299)  ← stdin/stdout NDJSON (stream-json)
   │  ~/.claude/projects/<proje>/<cliSessionId>.jsonl  (asıl transkript)
```

### 2. CLI'ı başlatma bayrakları (SDK, `index.chunk-DNyequwM.js`)

SDK, her sorgu için şu bayrakları sabit olarak ekliyor: `["--output-format","stream-json","--verbose","--input-format","stream-json"]`. Seçeneklere göre eklenen bayraklar şunlar:
`--model`, `--effort`, `--max-turns`, `--max-budget-usd`, `--task-budget`, `--max-thinking-tokens` / `--thinking=adaptive|disabled`, `--thinking-display`, `--agent`, `--permission-mode`, `--permission-prompt-tool` (`=stdio`), `--allow-dangerously-skip-permissions`, `--resume`, `--resume-session-at`, `--continue`, `--fork-session`, `--session-id`, `--no-session-persistence`, `--mcp-config`, `--strict-mcp-config`, `--setting-sources`, `--managed-settings`, `--add-dir`, `--plugin-dir`, `--tools`, `--json-schema`, `--fallback-model`, `--include-partial-messages`, `--include-hook-events`, `--await-initialize`, `--debug-file`, `--betas`.
Ortam değişkenleri: `CLAUDE_CODE_ENTRYPOINT` (masaüstü için `claude-desktop`, Cowork için `local-agent`; SDK varsayılanı `sdk-ts`) ve `CLAUDE_AGENT_SDK`.

### 3. Akış protokolü (stdin/stdout NDJSON)

- **stdin → CLI:** `{"type":"user","message":{...}}` satırları (`streamInput`), ayrıca `{"type":"control_request","request_id":..., "request":{"subtype":...}}`.
- **Masaüstü/SDK'dan CLI'a giden kontrol istekleri (seçilmiş):** `initialize` (hooks, sdkMcpServers, systemPrompt, appendSystemPrompt, jsonSchema...), `interrupt`, `set_permission_mode`, `set_model`, `set_max_thinking_tokens`, `rewind_files`, `mcp_status`, `mcp_set_servers`, `mcp_reconnect`, `mcp_toggle`, `mcp_authenticate`, `get_context_usage`, `get_usage`, `get_settings`, `update_settings`, `apply_flag_settings`, `reload_skills`, `reload_plugins`, `generate_session_title`, `rename_session`, `stop_task`, `background_tasks`, `side_question`, `set_cwd`, `export_conversation`, `remote_control`. Tam liste 55'ten fazla subtype içeriyor.
- **CLI'dan SDK'ya gelen kontrol istekleri:**
  - `can_use_tool`: alanları `tool_name`, `input`, `permission_suggestions`, `blocked_path`, `decision_reason`, `tool_use_id`, `mcp_server`. Cevap `{behavior:"allow", updatedInput, updatedPermissions?}` ya da `{behavior:"deny", message}`.
  - `hook_callback` (`callback_id`, `input`, `tool_use_id`): SDK'da kayıtlı JS hook fonksiyonu çalıştırılıyor.
  - `mcp_message` (`server_name`, `message`): SDK içi (in-process) MCP sunucusuna JSON-RPC iletiliyor.
  - `elicitation`, `request_user_dialog`.
- **stdout ← CLI:** `system` (init: session_id, araçlar, MCP durumu), `assistant`, `user` (tool_result), `stream_event` (`--include-partial-messages` ile kısmi metin), `result` (maliyet, süre, session_id), `control_response`, `control_cancel_request`.
- Masaüstü ayrıca `--attach-serve <id> --input-format stream-json --output-format stream-json` ile çalışan bir "tool host helper" kullanıyor (`index.chunk-BFxRKxih.js`). Bu yapı, uzak (bulut) oturumların araçlarını yerel makinede çalıştırmaya yarıyor.

### 4. İzinler

- Mod seçimi oturum başına tutuluyor (`permissionMode` alanı) ve canlı olarak `set_permission_mode` ile değiştiriliyor (`setPermissionMode(` 24 çağrı yeri).
- İzin isteği akışı: CLI `can_use_tool` gönderir → SDK `canUseTool` geri çağrısı çalışır → ana süreç `pendingPermissions` kaydını açar ve arayüze `onToolPermissionRequest` gönderir → kullanıcı kartta karar verir (`respondToToolPermission(id, "allow"|"deny", {...}, "card")`) → karar CLI'a döner. "Her zaman izin ver" kararları oturum kaydına yazılıyor (`sessionPermissionUpdates`, `alwaysAllowedReasons`).
- `bypassPermissions` için hesap bazlı ayrı bir kapı (gate) ve kullanıcı onayı var (`bypassPermissionsGateByAccount`, `bypassPermissionsOptInByAccount`).
- Cowork/HostLoop kendi kurallarını ekliyor: `disallowedTools` artı deny kuralları, `toolAliases:{Bash, WebFetch}` yönlendirmesi, yazılabilir yol listesi.
- Yardımcı tek atışlık ajanlarda `canUseTool:async()=>({behavior:"deny"})` kullanılıyor, yani araç tamamen yasak.

### 5. Hook'lar

SDK, hook'ları `initialize` isteğinin `hooks` alanıyla kaydediyor. CLI, hook olayı gerçekleşince `hook_callback` ile geri çağırıyor. Kodda görülen olay adları `PreToolUse`, `PostToolUse` ve `PermissionRequest`. `--include-hook-events` bayrağı hook olaylarını akışa da yansıtıyor. Kullanıcının `settings.json` hook'ları ise CLI tarafında çalışmaya devam ediyor (`--setting-sources`).

### 6. Oturum devamı

- Masaüstü kendi oturum kimliğini (`sessionId`) CLI oturum kimliğinden (`cliSessionId`) ayrı tutuyor. Devam ettirirken `--resume <cliSessionId>` gönderiyor. Çatallamada `--fork-session`, belli bir noktadan devamda `--resume-session-at` kullanılıyor.
- Transkript okuma doğrudan `~/.claude/projects/.../<cliSessionId>.jsonl` dosyasından yapılıyor. Ayrı bir `transcript-search-worker` arama yapıyor.
- `toolSurfaceSnapshot.cliVersion` ile CLI sürümü değişince oturumun araç yüzeyi yeniden değerlendiriliyor. `getClaudeCodeRestartVersions` ve `applyModelByRestart` gibi akışlar var.

### 7. MCP yapılandırması

- Kullanıcı MCP'leri `--mcp-config` (JSON) ile, uygulamanın kendi araçları ise `createSdkMcpServer` ile (süreç içi, `type:"sdk"`) veriliyor. Uzak oturumlarda ve CLI launcher'da `strictMcpConfig=true` zorlanıyor.
- Komut satırı uzunluk sınırı için ayrı bir bütçe hesabı var: `allowed_tools`, `mcp_config` ve `settings` uzunlukları ölçülüyor (`index.chunk-M6SkuaH9.js` `UM()`). Windows'ta komut satırı sınırına takılmamak için önemli.

### 8. Sürüm ve uyum sözleşmesi ("harnessSchema")

Uygulamanın içinde CLI manifesti gömülü. Bu manifest sürümü, platform başına `claude.exe.zst` dosyasını, sha256 özetini ve `sdkCompat{testedWrapperVersions, harnessSchema:1}` alanını tanımlıyor. Uygulama yalnız test edilmiş SDK sarmalayıcı sürümüyle uyumlu CLI'ı kullanıyor, gerekirse indiriyor. Böylece kullanıcının PATH'teki `claude.exe`'si (burada 2.1.296) ile masaüstünün kullandığı CLI (2.1.299) birbirinden bağımsız kalıyor.

## Yapay Zeka Merkezi için somut öneriler

Öncelik sırasına göre:

1. **Kalıcı çift yönlü Claude oturumu.** `claude_motoru.py`, her tur için yeni süreç açmak yerine oturum başına tek bir `claude` süreci tutmalı. Komut: `claude --output-format stream-json --input-format stream-json --verbose --include-partial-messages ...` (`-p` olmadan da aynı protokol çalışır; SDK `-p` vermiyor). Uygulama: `taban.py` içinde `Popen(stdin=PIPE)` sürecini oturum sözlüğünde sakla. Her kullanıcı mesajını `{"type":"user","message":{"role":"user","content":[...]}}` satırı olarak yaz. stdout'u bir iş parçacığında satır satır okuyup SSE ile arayüze ilet.
2. **İzin kartları (`--permission-prompt-tool stdio`).** Araçları açıp her araç isteğini kullanıcıya sormak için CLI'a `--permission-prompt-tool stdio` ver. Gelen `control_request{subtype:"can_use_tool"}` satırını arayüzde "İzin ver / Reddet / Her zaman" kartı olarak göster. Cevabı `{"type":"control_response","response":{"subtype":"success","request_id":..., "response":{"behavior":"allow","updatedInput":{...}}}}` olarak stdin'e yaz. Yusuf'un silme/anahtar kuralları bu noktada ek bir Python denetimiyle (`guvenlik.py`) zorlanabilir.
3. **Kesme ve canlı ayar değişimi.** "Durdur" düğmesi süreci öldürmek yerine `control_request{subtype:"interrupt"}` göndermeli. Model veya izin modu değişince `set_model` ve `set_permission_mode` gönderilmeli. Böylece oturum ve önbellek korunur.
4. **İki katmanlı oturum kaydı.** Masaüstündeki `local_<uuid>.json` yapısını örnek al: `{merkez_oturum_id, cli_oturum_id, motor, cwd, model, izin_modu, baslik, son_etkinlik, kalici_izinler, tur_ozeti}`. Transkripti kopyalama, `~/.claude/projects/...jsonl` dosyasından oku. Devam için `--resume`, çatallama için `--fork-session` kullan.
5. **İzin modu seçici.** Arayüze `default / acceptEdits / plan / dontAsk / bypassPermissions` seçicisi ekle. `bypassPermissions`'ı Yusuf'un açık onayına bağla; masaüstündeki `bypassPermissionsGate` buna örnek.
6. **Uygulamanın kendi MCP araçları.** Masaüstündeki `ccd_*` sunucularına benzer şekilde Merkez'in yeteneklerini küçük bir stdio MCP sunucusu (Python, stdlib JSON-RPC) olarak `--mcp-config` ile ver. Örnek araçlar: `hafiza_ara`, `pencere_ac`, `jev_puanla`. Böylece Claude, Merkez'i araçla yönetebilir. Codex ve Gemini de aynı MCP'yi kullanabilir.
7. **Oturum başına git worktree.** Kod işi yapan oturumlar için `git worktree add --no-checkout -b <dal> .claude/worktrees/<ad>` aç. Bitince öner ama silme; silme kararı Yusuf'un ve yalnız çöp kutusuna. Paralel motorların aynı dosyalarda çakışması önlenir.
8. **CLI sürüm sabitleme ve uyum denetimi.** Masaüstündeki `harnessSchema` fikrini uygula: `saglayicilar.json` dosyasına motor başına `test_edilen_surum` ekle. Açılışta `claude --version` / `codex --version` sonucunu karşılaştır ve uyumsuzlukta uyarı ver (`guncelleme.py` ile birleştirilebilir).
9. **Yan paneller.** Terminal paneli (Python'da `pywinpty` gerekir; stdlib ile zor, opsiyonel), dosya paneli (salt okunur listeleme ve önizleme), git diff paneli (`git diff --stat` + dosya yaması). Önizleme için mevcut `cdp.py` / Edge CDP ile "dev server algıla + ekran görüntüsü" eklenebilir.
10. **Tek atışlık yardımcı ajanlar.** Başlık üretimi ve tur özeti (`postTurnSummary{status_category, needs_action}`) için ucuz modelle araçsız ve kalıcı oturumsuz çağrı yap: `--tools "" --no-session-persistence --max-turns 1`. Kenar çubuğunda "işlem bekliyor" rozeti gösterilebilir.
11. **Windows komut satırı bütçesi.** Uzun MCP/izin listelerini argüman yerine dosya üzerinden ver: `--mcp-config <dosya>`, `--settings <dosya>`. Masaüstü de bu sınırı ölçüyor.

## Belirsiz noktalar

- `ion-dist` arayüzü yerel paket olarak yükleniyor, ancak claude.ai sunucusundan dinamik yapılandırma da alıyor (`discoveredRendererConfig`). Hangi ekranların tamamen yerel çalıştığı statik analizle kesinleşmedi.
- Hook olaylarından kodda yalnız `PreToolUse`, `PostToolUse` ve `PermissionRequest` görüldü. Diğer olayların SDK üzerinden kullanılıp kullanılmadığı belirsiz; CLI'ın kendisi daha fazlasını destekliyor.
- `--permission-prompts`, `--session-mirror`, `--channels`, `--project-config-root`, `--resume-drops-turn` bayraklarının anlamı ve kararlılığı belgelenmemiş olabilir. Bunlar SDK ile CLI arasındaki iç bayraklar; Merkez'de kullanmadan önce `claude --help` ile doğrulanmalı.
- Cowork VM'inin (`cowork-svc.exe`, vhdx) iç yapısı incelenmedi; ikili analiz gerektirir.
- Kod adları (`sableOtter`, `copperHeron`, `GrandPrix`, `ViolinFret`, `Gorse`) özellik bayrağı arkasındaki deneysel işler gibi görünüyor; işlevleri doğrulanmadı.
- Çalışan uygulamaya CDP/çalışma zamanı ile bağlanılmadı (fuses `--inspect`'i kapatıyor; uygulama kapatılmadı). Tüm bulgular statik.

## Kullanılan araçlar ve tahmini token

- REA: `inspect_electron_fuses` (claude.exe). Diğer REA araçları gerekmedi; asar çıkarma `npx @electron/asar extract` ile yalnız scratchpad'e yapıldı (`...\scratchpad\claude-asar\out`). Uygulama klasörüne yazılmadı.
- Bash: grep/dd/ls ile dizgi taraması. Python yalnız `-I` ile JSON anahtar yapısı için çalıştırıldı; değerler okunmadı. `buddy-tokens.json`, `config.json`, Local Storage ve anahtar klasörü açılmadı.
- Yapay Zeka Merkezi'nden yalnız `motorlar/claude_motoru.py` bayrak satırları ve `arastirma/harness-arastirmasi.md` başlıkları okundu.
- Tahmini token: yaklaşık 70 bin girdi, 12 bin çıktı.
