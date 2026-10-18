import clsx, { type ClassValue } from "clsx";
import type { TFunction } from "i18next";
import { ApiError, type Lang } from "./api";

export const cn = (...v: ClassValue[]) => clsx(v);

const LOCALE: Record<Lang, string> = { en: "en-IN", ta: "ta-IN", bn: "bn-IN", te: "te-IN" };
export const localeOf = (lang: string) => LOCALE[(lang as Lang)] ?? "en-IN";

export function fmtNumber(n: number | null | undefined, lang: string, opts: Intl.NumberFormatOptions = {}) {
  if (n === null || n === undefined || Number.isNaN(n)) return "-";
  return new Intl.NumberFormat(localeOf(lang), { maximumFractionDigits: 1, ...opts }).format(n);
}

/** 138,000,000 -> "13.8 crore"/"138 M": we use millions everywhere for simplicity. */
export function fmtMillions(n: number | null | undefined, lang: string) {
  if (n === null || n === undefined) return "-";
  if (Math.abs(n) >= 1_000_000) return fmtNumber(n / 1_000_000, lang, { maximumFractionDigits: 1 }) + " M";
  if (Math.abs(n) >= 1_000) return fmtNumber(n / 1_000, lang, { maximumFractionDigits: 1 }) + " K";
  return fmtNumber(n, lang, { maximumFractionDigits: 0 });
}

export function fmtDate(iso: string | null | undefined, lang: string, opts: Intl.DateTimeFormatOptions = { day: "numeric", month: "short", year: "numeric" }) {
  if (!iso) return "-";
  const d = new Date(iso.length === 10 ? iso + "T00:00:00" : iso);
  if (Number.isNaN(d.getTime())) return iso;
  return new Intl.DateTimeFormat(localeOf(lang), opts).format(d);
}

export function fmtTime(iso: string, lang: string) {
  const d = new Date(iso);
  const today = new Date();
  const sameDay = d.toDateString() === today.toDateString();
  return new Intl.DateTimeFormat(localeOf(lang), sameDay ? { hour: "2-digit", minute: "2-digit" } : { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" }).format(d);
}

export function relTime(iso: string, lang: string) {
  const diff = (new Date(iso).getTime() - Date.now()) / 1000;
  const rtf = new Intl.RelativeTimeFormat(localeOf(lang), { numeric: "auto" });
  const abs = Math.abs(diff);
  if (abs < 60) return rtf.format(Math.round(diff), "second");
  if (abs < 3600) return rtf.format(Math.round(diff / 60), "minute");
  if (abs < 86400) return rtf.format(Math.round(diff / 3600), "hour");
  return rtf.format(Math.round(diff / 86400), "day");
}

export const todayISO = () => new Date().toISOString().slice(0, 10);

/** Maps API errors to a translated message (global error handling rule). */
export function errorMessage(e: unknown, t: TFunction): string {
  if (e instanceof ApiError) {
    switch (e.status) {
      case 0: return t("errors.network");
      case 401: return t("errors.unauthorized");
      case 403: return t("errors.forbidden");
      case 404: return t("errors.notFound");
      case 422: {
        const d = e.detail;
        if (typeof d === "string") return d;
        if (Array.isArray(d) && d[0]?.msg) return String(d[0].msg);
        return t("errors.validation");
      }
      case 429: return t("errors.tooMany");
      default: return typeof e.detail === "string" ? e.detail : t("errors.generic");
    }
  }
  return t("errors.generic");
}

/** The latest non-null value of a field across labs (oldest -> newest order expected). */
export function latest<T extends Record<string, any>>(rows: T[], key: keyof T): number | undefined {
  for (let i = rows.length - 1; i >= 0; i--) {
    const v = rows[i][key];
    if (v !== null && v !== undefined) return v as number;
  }
  return undefined;
}

export const clamp = (n: number, lo: number, hi: number) => Math.max(lo, Math.min(hi, n));
export const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));
export const uid = () => Math.random().toString(36).slice(2, 10);

/** Stage colour used in charts and chips. */
export function stageColor(g: string | null | undefined) {
  switch (g) {
    case "G1": return "#10b981";
    case "G2": return "#65a30d";
    case "G3a": return "#d97706";
    case "G3b": return "#ea580c";
    case "G4": return "#dc2626";
    case "G5": return "#9f1239";
    default: return "#64748b";
  }
}

/** Typed-safe translation with interpolation params (i18next return types are wide). */
export const tx = (t: TFunction, key: string, opts?: Record<string, unknown>): string => String((t as any)(key, opts));
