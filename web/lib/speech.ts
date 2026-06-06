// PB — Synthèse vocale (TTS) : Magellan lit ses réponses à voix haute.
// 100 % navigateur (Web Speech `speechSynthesis`), aucune dépendance.

export function ttsSupported(): boolean {
  return typeof window !== "undefined" && "speechSynthesis" in window;
}

// Retire le markdown/emoji pour une lecture vocale propre (pas de « astérisque »,
// « dièse », etc.). Best-effort, volontairement simple.
export function plainForSpeech(text: string): string {
  return text
    .replace(/```[\s\S]*?```/g, " ")
    .replace(/`([^`]+)`/g, "$1")
    .replace(/!?\[([^\]]*)\]\([^)]*\)/g, "$1") // liens / images → libellé
    .replace(/[*_#>~|]/g, " ")
    .replace(/^[-•]\s+/gm, "")
    .replace(/\s*={3,}ACTIONS={3,}.*$/is, "") // garde-fou si la ligne ===ACTIONS=== fuit
    .replace(
      /[\u{1F000}-\u{1FAFF}\u{2600}-\u{27BF}\u{2190}-\u{21FF}\u{2B00}-\u{2BFF}️]/gu,
      " ",
    )
    .replace(/\s+/g, " ")
    .trim();
}

// Référence retenue volontairement : sans elle, Chrome peut collecter
// l'utterance avant que `onend` ne se déclenche (bug connu). Write-only à dessein.
let currentUtterance: SpeechSynthesisUtterance | null = null;

// Lit `text` à voix haute (fr-FR). Annule toute lecture en cours.
// `onend` est appelé à la fin (ou en cas d'échec) — utile pour réenchaîner
// l'écoute en mode déplacement.
export function speak(text: string, onend?: () => void): void {
  if (!ttsSupported()) {
    onend?.();
    return;
  }
  const clean = plainForSpeech(text);
  if (!clean) {
    onend?.();
    return;
  }
  try {
    window.speechSynthesis.cancel();
    const u = new SpeechSynthesisUtterance(clean);
    u.lang = "fr-FR";
    u.rate = 1.05;
    u.pitch = 1;
    u.onend = () => {
      currentUtterance = null;
      onend?.();
    };
    u.onerror = () => {
      currentUtterance = null;
      onend?.();
    };
    currentUtterance = u;
    window.speechSynthesis.speak(u);
  } catch {
    currentUtterance = null;
    onend?.();
  }
}

export function stopSpeaking(): void {
  if (!ttsSupported()) return;
  try {
    window.speechSynthesis.cancel();
  } catch {
    /* no-op */
  }
  currentUtterance = null;
}
