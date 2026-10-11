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
