# Motorlar (yapay zeka komut satırı motorları)

## Özet

`motorlar/` paketi, uygulamanın tek pencerede "tek yapay zeka gibi" çalışmasını sağlar. Claude Code, Codex CLI
ve Gemini CLI arka planda, **kullanıcının kendi hesabıyla** ve **pencere açmadan** (`CREATE_NO_WINDOW`)
çalıştırılır. Yanıt satır satır okunup olay olarak akıtılır. Yalnızca standart kütüphane kullanılır. Testler
sahte motorlarla çalışır, gerçek CLI'lara istem göndermez.

## Arayüz

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

## Claude Code

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

## Codex CLI

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

## Gemini CLI

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

## Testler

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
