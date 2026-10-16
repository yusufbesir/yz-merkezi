// Bu dosya Yusuf'a (yusufbesir) ait Yapay Zeka Merkezi projesinin parçasıdır.
// Yapay zeka ajanları bu dosyayı Yusuf'un kuralları çerçevesinde inceleyip değiştirebilir; silme kararı yalnız Yusuf'undur
// ve silme yalnızca Geri Dönüşüm Kutusu'na taşıyarak yapılır, kalıcı silme yoktur.
// Kurallar: BENIOKU.md (Yapay zekalar için notlar) ve D:\YusufII\HAFIZAM1\kasa\ORTAK-AJAN-KURALLARI.md.

// Testler için sahte site betiği (CSP satır içi script'e izin vermediğinden ayrı dosya).
  const sohbet = document.getElementById("sohbet");
  const kutu = document.getElementById("prompt-textarea");
  const dugme = document.querySelector('[data-testid="send-button"]');

  function mesajEkle(rol, metin) {
    const e = document.createElement("div");
    e.setAttribute("data-message-author-role", rol);
    e.textContent = metin;
    sohbet.appendChild(e);
    sohbet.scrollTop = sohbet.scrollHeight;
  }

  // /test/c/<kimlik> adresinde hazır bir sohbet (bir soru, bir yanıt) yüklenir.
  const eslesme = /\/c\/([^/?#]+)/.exec(location.pathname);
  if (eslesme) {
    mesajEkle("user", "Soru " + eslesme[1]);
    mesajEkle("assistant", "Yanıt " + eslesme[1]);
    const bag = document.querySelector('nav a[href$="/c/' + eslesme[1] + '"]');
    if (bag) { bag.setAttribute("aria-current", "page"); }
  }

  function yolla() {
    const metin = kutu.innerText.trim();
    if (!metin) { return; }
    mesajEkle("user", metin);
    // ChatGPT gibi: yeni sohbet sayfasında ilk mesajdan sonra adres /c/<kimlik> olur (sayfa yenilenmeden).
    if (!/\/c\//.test(location.pathname)) { history.pushState({}, "", "/test/c/y" + Date.now()); }
    kutu.innerText = "";
    dugme.disabled = true;
    const durdur = document.createElement("button");
    durdur.setAttribute("type", "button");
    durdur.setAttribute("aria-label", "Stop");
    durdur.textContent = "■";
    document.getElementById("alt").appendChild(durdur);
    setTimeout(() => {
      mesajEkle("assistant", "Yanıt: " + metin);
      durdur.remove();
    }, 1000);
  }

  kutu.addEventListener("input", () => { dugme.disabled = kutu.innerText.trim() === ""; });
  kutu.addEventListener("keydown", (o) => {
    if (o.key === "Enter" && !o.shiftKey) { o.preventDefault(); yolla(); }
  });
  // Düğme form içinde: tıklama submit olayını tetikler; sayfa yenilenmesin, mesaj yollansın.
  document.getElementById("alt").addEventListener("submit", (o) => { o.preventDefault(); yolla(); });

  // Geri bildirim formu: gönderilirse sayaç artar ve metin kaydedilir (testler "yanlış forma gitmedi"yi buradan doğrular).
  const geriForm = document.getElementById("geri-bildirim");
  const geriDurum = document.getElementById("geri-bildirim-durum");
  geriForm.addEventListener("submit", (o) => {
    o.preventDefault();
    const n = Number(geriDurum.dataset.gonderilen) + 1;
    geriDurum.dataset.gonderilen = String(n);
    geriDurum.dataset.metin = document.getElementById("geri-bildirim-metin").value;
    geriDurum.textContent = "Gönderildi (" + n + ")";
  });

  // Model seçici (ChatGPT benzeri): düğme tıklanınca role=menu içinde üç menuitem açılır; birine tıklanınca düğme
  // metni değişir ve menü kapanır; Escape ya da menü dışına tıklama da kapatır.
  const modelDugmesi = document.getElementById("model-dugmesi");
  modelDugmesi.style.width = "auto";  // sayfa stili (CSP) tüm düğmeleri yuvarlak yapar; CSSOM ile ezilir
  modelDugmesi.style.borderRadius = "8px";
  modelDugmesi.style.padding = "0 12px";
  const MODELLER = ["GPT-5 Deneme", "GPT-5 mini", "o-deneme"];
  let modelMenusu = null;

  function modelMenusunuKapat() {
    if (modelMenusu) { modelMenusu.remove(); modelMenusu = null; }
    modelDugmesi.setAttribute("aria-expanded", "false");
  }

  function modelMenusunuAc() {
    modelMenusu = document.createElement("div");
    modelMenusu.setAttribute("role", "menu");
    modelMenusu.style.position = "absolute";
    modelMenusu.style.top = "44px";
    modelMenusu.style.left = "240px";
    modelMenusu.style.background = "#fff";
    modelMenusu.style.border = "1px solid #ccc";
    modelMenusu.style.padding = "4px";
    modelMenusu.style.zIndex = "10";
    const secili = modelDugmesi.textContent.trim();
    MODELLER.forEach((ad) => {
      const oge = document.createElement("div");
      oge.setAttribute("role", "menuitem");
      oge.setAttribute("tabindex", "-1");
      oge.setAttribute("aria-checked", ad === secili ? "true" : "false");
      oge.style.padding = "6px 10px";
      oge.style.cursor = "pointer";
      oge.textContent = ad;
      oge.addEventListener("click", () => {
        modelDugmesi.textContent = ad;
        modelMenusunuKapat();
      });
      modelMenusu.appendChild(oge);
    });
    document.body.appendChild(modelMenusu);
    modelDugmesi.setAttribute("aria-expanded", "true");
  }

  modelDugmesi.addEventListener("click", () => { if (modelMenusu) { modelMenusunuKapat(); } else { modelMenusunuAc(); } });
  document.addEventListener("keydown", (o) => { if (o.key === "Escape" && modelMenusu) { modelMenusunuKapat(); } });
  document.addEventListener("pointerdown", (o) => {
    if (modelMenusu && !modelMenusu.contains(o.target) && o.target !== modelDugmesi) { modelMenusunuKapat(); }
  });
