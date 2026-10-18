import { Languages } from "lucide-react";
import { useState, useSyncExternalStore, type ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { api, type Lang } from "@/lib/api";
import { cn } from "@/lib/utils";
import { useSession } from "@/store/session";

/** Chat translation: turns every message, post and AI answer into the language chosen in the globe popup.
 *  Texts are batched into one request, cached per language in memory (and on the server), and the original stays one click away. */
const cache = new Map<string, string>();
const pending = new Set<string>();
let timer: ReturnType<typeof setTimeout> | null = null;
let version = 0;
let unavailable = false;
const subs = new Set<() => void>();
const bump = () => { version++; subs.forEach((f) => f()); };
const key = (lang: string, text: string) => `${lang}\u0000${text}`;

async function flush() {
  timer = null;
  const batch = [...pending].slice(0, 40);
  batch.forEach((k) => pending.delete(k));
  const byLang = new Map<string, string[]>();
  for (const k of batch) { const [lang, text] = k.split("\u0000"); byLang.set(lang, [...(byLang.get(lang) ?? []), text]); }
  for (const [lang, texts] of byLang) {
    try {
      const r = await api.translate(texts, lang as Lang);
      unavailable = !r.available;
      texts.forEach((t, i) => cache.set(key(lang, t), r.translated[i] ? r.translations[i] : t));
    } catch {
      texts.forEach((t) => cache.set(key(lang, t), t));
    }
  }
  bump();
  if (pending.size) timer = setTimeout(flush, 30);
}

export function useTranslated(text: string): { text: string; translated: boolean; loading: boolean } {
  const on = useSession((s) => s.translateOn);
  const { i18n } = useTranslation();
  const lang = (["en", "ta", "bn", "te"].includes(i18n.language) ? i18n.language : "en") as Lang;
  useSyncExternalStore((cb) => { subs.add(cb); return () => subs.delete(cb); }, () => version);
  if (!on || !text.trim()) return { text, translated: false, loading: false };
  const k = key(lang, text);
  const hit = cache.get(k);
  if (hit === undefined) {
    if (!pending.has(k)) { pending.add(k); if (!timer) timer = setTimeout(flush, 60); }
    return { text, translated: false, loading: true };
  }
  return { text: hit, translated: hit !== text, loading: false };
}

export const translationUnavailable = () => unavailable;

/** Inline translated text. Click the small icon to see the original. */
export function Tx({ text, className, as: As = "span", render }: { text: string; className?: string; as?: "span" | "p" | "div"; render?: (t: string) => ReactNode }) {
  const { text: out, translated, loading } = useTranslated(text);
  const [orig, setOrig] = useState(false);
  const shown = orig ? text : out;
  return (
    <As className={cn(className, loading && "opacity-70")}>
      {render ? render(shown) : shown}
      {translated && (
        <button type="button" onClick={() => setOrig((v) => !v)} className="ml-1 inline-flex align-middle text-[color:var(--muted)] opacity-70 hover:opacity-100" title={orig ? "Show translation" : "Translated. Click for the original."} aria-label="toggle original" data-testid="tx-toggle">
          <Languages className="h-3.5 w-3.5" />
        </button>
      )}
    </As>
  );
}

/** Switch used in the top bar and in chat headers. */
export function TranslateToggle({ compact = false }: { compact?: boolean }) {
  const on = useSession((s) => s.translateOn);
  const toggle = useSession((s) => s.toggleTranslate);
  const { t, i18n } = useTranslation();
  const names: Record<string, string> = { en: "English", ta: "தமிழ்", bn: "বাংলা", te: "తెలుగు" };
  return (
    <button type="button" onClick={toggle} aria-pressed={on} data-testid="translate-toggle"
      title={on ? `Translating chats into ${names[i18n.language] ?? i18n.language}` : "Translate chats into my language"}
      className={cn("inline-flex min-h-[40px] items-center gap-1.5 rounded-xl px-3 text-sm font-semibold transition", on ? "bg-accent text-[color:var(--on-accent)]" : "btn-ghost !min-h-[40px] !px-3")}>
      <Languages className="h-4 w-4" />{!compact && <span className="hidden sm:inline">{on ? (names[i18n.language] ?? "On") : t("transplant.translateOff", "Translate")}</span>}
    </button>
  );
}
