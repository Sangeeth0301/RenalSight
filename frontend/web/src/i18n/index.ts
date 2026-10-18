import i18n from "i18next";
import { initReactI18next } from "react-i18next";
import en from "./en.json";
import ta from "./ta.json";
import bn from "./bn.json";
import te from "./te.json";
import { api, auth, type Lang } from "@/lib/api";

export const LANGS: Lang[] = ["en", "ta", "bn", "te"];
export const SPEECH_LOCALE: Record<Lang, string> = { en: "en-IN", ta: "ta-IN", bn: "bn-IN", te: "te-IN" };
const KEY = "renalsight_lang";
const saved = (() => { try { return localStorage.getItem(KEY) as Lang | null; } catch { return null; } })();

i18n.use(initReactI18next).init({
  resources: { en: { translation: en }, ta: { translation: ta }, bn: { translation: bn }, te: { translation: te } },
  lng: saved && LANGS.includes(saved) ? saved : "en",
  fallbackLng: "en", // doctor.* and admin.* exist only in English
  interpolation: { escapeValue: false },
  returnNull: false,
});
document.documentElement.lang = i18n.language;

/** One-click language change: instant, offline, no API key. Saves locally and, if signed in, to the profile. */
export async function setLanguage(lang: Lang) {
  await i18n.changeLanguage(lang);
  document.documentElement.lang = lang;
  try { localStorage.setItem(KEY, lang); } catch { /* ignore */ }
  if (auth.token) {
    try { await api.updateProfile({ language: lang }); } catch { /* offline: local choice still applies */ }
  }
}
export const hasChosenLanguage = () => { try { return !!localStorage.getItem(KEY); } catch { return false; } };
export const currentLang = (): Lang => (LANGS.includes(i18n.language as Lang) ? (i18n.language as Lang) : "en");
export default i18n;
