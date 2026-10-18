import { create } from "zustand";
import { api, ApiError, auth, type KidneyState, type User } from "@/lib/api";

export type Theme = "healthy" | "watch" | "critical";
export interface Toast { id: number; kind: "ok" | "error" | "info"; text: string }

function applyRole(r: string | null) {
  if (r) document.documentElement.setAttribute("data-role", r); else document.documentElement.removeAttribute("data-role");
}
function applyTheme(t: Theme) {
  document.documentElement.setAttribute("data-theme", t);
}
export type Mode = "light" | "dark";
function applyMode(m: Mode) { document.documentElement.setAttribute("data-mode", m); }
function initialMode(): Mode {
  try {
    const v = localStorage.getItem("renalsight_mode");
    if (v === "light" || v === "dark") return v;
    return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  } catch { return "light"; }
}
const readBool = (k: string) => { try { return localStorage.getItem(k) === "1"; } catch { return false; } };
const writeBool = (k: string, v: boolean) => { try { localStorage.setItem(k, v ? "1" : "0"); } catch { /* ignore */ } };

interface SessionState {
  user: User | null;
  ready: boolean;
  theme: Theme;
  mode: Mode;
  toggleMode: () => void;
  kidney: KidneyState | null;
  largeText: boolean;
  highContrast: boolean;
  translateOn: boolean;
  toggleTranslate: () => void;
  toasts: Toast[];
  langOpen: boolean;
  setLangOpen: (v: boolean) => void;
  init: () => Promise<void>;
  setUser: (u: User | null) => void;
  logout: () => void;
  setKidney: (k: KidneyState | null) => void;
  toggleLargeText: () => void;
  toggleHighContrast: () => void;
  toast: (kind: Toast["kind"], text: string) => void;
  dismissToast: (id: number) => void;
}

let toastId = 1;

export const useSession = create<SessionState>((set, get) => ({
  user: null,
  ready: false,
  theme: "healthy",
  mode: initialMode(),
  toggleMode() {
    const m: Mode = get().mode === "dark" ? "light" : "dark";
    try { localStorage.setItem("renalsight_mode", m); } catch { /* ignore */ }
    applyMode(m);
    set({ mode: m });
  },
  kidney: null,
  largeText: readBool("renalsight_large"),
  highContrast: readBool("renalsight_contrast"),
  translateOn: readBool("renalsight_translate"),
  toggleTranslate() { const v = !get().translateOn; writeBool("renalsight_translate", v); set({ translateOn: v }); },
  toasts: [],
  langOpen: false,
  setLangOpen: (v) => set({ langOpen: v }),

  async init() {
    document.documentElement.classList.toggle("large-text", get().largeText);
    document.documentElement.classList.toggle("high-contrast", get().highContrast);
    applyMode(get().mode);
    applyTheme(get().theme);
    if (!auth.token) { set({ ready: true }); return; }
    try {
      const u = await api.me();
      applyRole(u.role);
      set({ user: u, ready: true });
    } catch (e) {
      // only an expired / invalid token logs the user out; being offline or the server being down keeps the token
      if (e instanceof ApiError && e.status === 401) auth.set(null);
      set({ user: null, ready: true });
    }
  },
  setUser: (u) => { applyRole(u?.role ?? null); set({ user: u }); },
  logout() {
    auth.set(null);
    try { if ("caches" in window) void caches.delete("rs-api-v1"); } catch { /* ignore */ }
    applyTheme("healthy");
    applyRole(null);
    set({ user: null, kidney: null, theme: "healthy" });
  },
  setKidney(k) {
    const theme: Theme = k && k.has_data ? k.theme : "healthy";
    applyTheme(theme);
    set({ kidney: k, theme });
  },
  toggleLargeText() {
    const v = !get().largeText;
    writeBool("renalsight_large", v);
    document.documentElement.classList.toggle("large-text", v);
    set({ largeText: v });
  },
  toggleHighContrast() {
    const v = !get().highContrast;
    writeBool("renalsight_contrast", v);
    document.documentElement.classList.toggle("high-contrast", v);
    set({ highContrast: v });
  },
  toast(kind, text) {
    const id = toastId++;
    set((s) => ({ toasts: [...s.toasts, { id, kind, text }] }));
    setTimeout(() => get().dismissToast(id), 4500);
  },
  dismissToast(id) { set((s) => ({ toasts: s.toasts.filter((t) => t.id !== id) })); },
}));
