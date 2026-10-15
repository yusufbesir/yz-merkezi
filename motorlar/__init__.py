"""Yapay zeka komut satırı motorları (Claude Code, Codex CLI, Gemini CLI).

Uygulama, kullanıcının kendi hesaplarıyla giriş yapılmış bu CLI'ları arka planda (pencere açmadan) çalıştırır
ve yanıtı olay sözlükleri hâlinde akıtır. Ayrıntı: motorlar/BENIOKU-motorlar.md.

Kullanım:
    from motorlar import motor
    m = motor("claude")
    m.hazir_mi()            # {"hazir", "sebep", "surum", "giris"}
    for olay in m.sor("Merhaba", oturum=None):
        ...
"""
from .claude_motoru import ClaudeMotoru
from .codex_motoru import CodexMotoru
from .gemini_motoru import GeminiMotoru
from .taban import Motor, MotorHatasi

MOTORLAR = {"claude": ClaudeMotoru, "codex": CodexMotoru, "gemini": GeminiMotoru}
_ORNEKLER = {}


def motor(kimlik):
    """Kimliği verilen motorun (tekil, önbellekli) örneği; bilinmeyen kimlikte MotorHatasi."""
    kimlik = str(kimlik or "").strip().lower()
    if kimlik not in MOTORLAR:
        raise MotorHatasi(f"Bilinmeyen motor: {kimlik or '(boş)'}")
    if kimlik not in _ORNEKLER:
        _ORNEKLER[kimlik] = MOTORLAR[kimlik]()
    return _ORNEKLER[kimlik]


__all__ = ["MOTORLAR", "Motor", "MotorHatasi", "motor", "ClaudeMotoru", "CodexMotoru", "GeminiMotoru"]
