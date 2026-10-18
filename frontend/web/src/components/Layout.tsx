import * as Popover from "@radix-ui/react-popover";
import { useQueryClient } from "@tanstack/react-query";
import {
  Accessibility, CalendarDays, Send, Moon, Sun, BookOpen, Building2, ChevronsLeft, ChevronsRight, DoorOpen, Download, FileText, FlaskConical, Globe, HeartPulse, Home, Hourglass, Inbox,
  LayoutDashboard, ListChecks, LogOut, Menu, MessageCircle, Pill, Settings, ShieldCheck, Stethoscope, Users, Bot, Newspaper, X, ClipboardList, MapPinned, HeartHandshake,
} from "lucide-react";
import { useEffect, useState, type ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { Link, NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import { useMyKidney } from "@/lib/hooks";
import { cn } from "@/lib/utils";
import { useSession } from "@/store/session";
import { TranslateToggle } from "@/lib/translate";
import { QuickSend } from "./QuickSend";
import { MiniKidney } from "./LivingKidney";
import { NotificationBell, useUnread } from "./NotificationBell";
import { Toasts } from "./ui";
import type { Role } from "@/lib/api";
import { api } from "@/lib/api";
import { useQuery } from "@tanstack/react-query";

interface Item { key: string; to: string; icon: ReactNode; badge?: number }
interface Group { key: string; items: Item[] }

const I = (c: ReactNode) => c;
function navFor(role: Role, queueCount: number): Group[] {
  const ic = "h-5 w-5 shrink-0";
  if (role === "doctor") {
    return [
      { key: "doctor", items: [
        { key: "dashboard", to: "/doctor", icon: I(<LayoutDashboard className={ic} />) },
        { key: "reviewQueue", to: "/doctor/queue", icon: I(<ClipboardList className={ic} />), badge: queueCount },
        { key: "schedule", to: "/doctor/schedule", icon: I(<CalendarDays className={ic} />) },
      ] },
      { key: "connect", items: [
        { key: "messages", to: "/chat", icon: I(<MessageCircle className={ic} />) },
        { key: "broadcast", to: "/hub/broadcast", icon: I(<Send className={ic} />) },
        { key: "consultRoom", to: "/rooms", icon: I(<DoorOpen className={ic} />) },
        { key: "agentInbox", to: "/inbox", icon: I(<Inbox className={ic} />) },
        { key: "community", to: "/community", icon: I(<Users className={ic} />) },
      ] },
      { key: "transplant", items: [{ key: "transplantHub", to: "/hub", icon: I(<HeartHandshake className={ic} />) }] },
      { key: "extras", items: [
        { key: "populationPulse", to: "/pulse", icon: I(<MapPinned className={ic} />) },
        { key: "researchDesk", to: "/research", icon: I(<BookOpen className={ic} />) },
        { key: "settings", to: "/settings", icon: I(<Settings className={ic} />) },
      ] },
    ];
  }
  if (role === "admin") {
    return [
      { key: "admin", items: [{ key: "adminPanel", to: "/admin", icon: I(<ShieldCheck className={ic} />) }, { key: "agentInbox", to: "/inbox", icon: I(<Inbox className={ic} />) }, { key: "community", to: "/community", icon: I(<Users className={ic} />) }] },
      { key: "transplant", items: [{ key: "transplantHub", to: "/hub", icon: I(<HeartHandshake className={ic} />) }] },
      { key: "extras", items: [
        { key: "populationPulse", to: "/pulse", icon: I(<MapPinned className={ic} />) },
        { key: "settings", to: "/settings", icon: I(<Settings className={ic} />) },
      ] },
    ];
  }
  const caregiver = role === "caregiver";
  return [
    { key: "platform", items: [
      { key: "home", to: "/home", icon: I(<Home className={ic} />) },
      ...(caregiver ? [] : [{ key: "reportGuidance", to: "/reports", icon: I(<FileText className={ic} />) }]),
      { key: "nephroBuddy", to: "/buddy", icon: I(<Bot className={ic} />) },
    ] },
    { key: "myKidney", items: [
      { key: "livingKidney", to: "/kidney", icon: I(<HeartPulse className={ic} />) },
      ...(caregiver ? [] : [
        { key: "timeMachine", to: "/forecast", icon: I(<Hourglass className={ic} />) },
        { key: "dailyRituals", to: "/rituals", icon: I(<ListChecks className={ic} />) },
        { key: "agentInbox", to: "/inbox", icon: I(<Inbox className={ic} />) },
      ]),
    ] },
    ...(caregiver ? [] : [{ key: "careWorkspace", items: [
      { key: "careLab", to: "/care", icon: I(<FlaskConical className={ic} />) },
      { key: "rxStudio", to: "/rx", icon: I(<Pill className={ic} />) },
    ] }]),
    { key: "connect", items: [
      { key: "directLine", to: "/chat", icon: I(<MessageCircle className={ic} />) },
      { key: "broadcast", to: "/hub/broadcast", icon: I(<Send className={ic} />) },
      { key: "consultRoom", to: "/rooms", icon: I(<DoorOpen className={ic} />) },
      { key: "community", to: "/community", icon: I(<Users className={ic} />) },
      { key: "careHub", to: "/care-hub", icon: I(<Building2 className={ic} />) },
    ] },
    { key: "transplant", items: [{ key: "transplantHub", to: "/hub", icon: I(<HeartHandshake className={ic} />) }] },
    { key: "extras", items: [
      { key: "populationPulse", to: "/pulse", icon: I(<MapPinned className={ic} />) },
      { key: "offlinePack", to: "/offline", icon: I(<Download className={ic} />) },
      { key: "researchDesk", to: "/research", icon: I(<Newspaper className={ic} />) },
      { key: "settings", to: "/settings", icon: I(<Settings className={ic} />) },
    ] },
  ];
}

function A11yMenu() {
  const { t } = useTranslation();
  const s = useSession();
  return (
    <Popover.Root>
      <Popover.Trigger asChild><button className="btn-ghost !px-3" aria-label={t("a11y.menu")} data-testid="a11y"><Accessibility className="h-5 w-5" /></button></Popover.Trigger>
      <Popover.Portal>
        <Popover.Content align="end" sideOffset={8} className="card z-[80] w-64 space-y-2 p-3 shadow-lift">
          {([["largeText", s.largeText, s.toggleLargeText], ["highContrast", s.highContrast, s.toggleHighContrast]] as const).map(([k, on, fn]) => (
            <label key={k} className="flex min-h-[44px] cursor-pointer items-center justify-between gap-3 rounded-xl px-2 hover:bg-[var(--surface-2)]">
              <span className="font-medium">{t(`a11y.${k}`)}</span>
              <input type="checkbox" checked={on} onChange={fn} className="h-5 w-5 accent-[var(--accent)]" />
            </label>
          ))}
        </Popover.Content>
      </Popover.Portal>
    </Popover.Root>
  );
}

export function TopBarActions() {
  const { t } = useTranslation();
  const setLangOpen = useSession((s) => s.setLangOpen);
  const mode = useSession((s) => s.mode);
  const toggleMode = useSession((s) => s.toggleMode);
  return (
    <>
      <TranslateToggle />
      <button className="btn-ghost !px-3" onClick={toggleMode} aria-label="Toggle dark mode" data-testid="mode">{mode === "dark" ? <Sun className="h-5 w-5" /> : <Moon className="h-5 w-5" />}</button>
      <button className="btn-ghost !px-3" onClick={() => setLangOpen(true)} aria-label={t("lang.change")} data-testid="globe"><Globe className="h-5 w-5" /></button>
    </>
  );
}

export function Layout() {
  const { t } = useTranslation();
  const user = useSession((s) => s.user)!;
  const logout = useSession((s) => s.logout);
  const kidney = useSession((s) => s.kidney);
  const nav = useNavigate();
  const qc = useQueryClient();
  const loc = useLocation();
  const [collapsed, setCollapsed] = useState(() => { try { return localStorage.getItem("renalsight_sidebar") === "1"; } catch { return false; } });
  const [drawer, setDrawer] = useState(false);
  const [qs, setQs] = useState(false);
  useMyKidney();
  useUnread();
  const queue = useQuery({ queryKey: ["doctor", "queue", "count"], queryFn: () => api.doctorQueue(), enabled: user.role === "doctor", refetchInterval: 30000 });
  const groups = navFor(user.role, queue.data?.length ?? 0);

  useEffect(() => setDrawer(false), [loc.pathname]);
  useEffect(() => { try { localStorage.setItem("renalsight_sidebar", collapsed ? "1" : "0"); } catch { /* ignore */ } }, [collapsed]);

  const sidebar = (mobile: boolean) => (
    <aside className={cn("rs-side flex h-full flex-col border-r border-line glass", mobile ? "w-72" : collapsed ? "w-[76px]" : "w-[260px]", "transition-[width] duration-200")}>
      <div className="flex h-16 items-center justify-between gap-2 px-4">
        <Link to="/" className="flex items-center gap-2 font-bold text-lg">
          <span className="grid h-9 w-9 place-items-center rounded-xl bg-accent-soft"><MiniKidney state={kidney} size={16} /></span>
          {(!collapsed || mobile) && <span>{t("app.name")}</span>}
        </Link>
        {mobile ? <button onClick={() => setDrawer(false)} className="btn-ghost !px-2" aria-label="close"><X className="h-5 w-5" /></button>
          : <button onClick={() => setCollapsed(!collapsed)} className="btn-ghost !px-2 hidden lg:inline-flex" aria-label="toggle sidebar">{collapsed ? <ChevronsRight className="h-5 w-5" /> : <ChevronsLeft className="h-5 w-5" />}</button>}
      </div>
      <nav className="flex-1 space-y-4 overflow-y-auto px-3 pb-4" aria-label="main">
        {groups.map((g) => (
          <div key={g.key}>
            {(!collapsed || mobile) && <p className="px-3 pb-1 text-[11px] font-bold uppercase tracking-wider text-muted">{t(`nav.groups.${g.key}`)}</p>}
            <ul className="space-y-0.5">
              {g.items.map((it) => (
                <li key={it.key}>
                  <NavLink to={it.to} end={it.to === "/doctor"} title={t(`nav.${it.key}`)}
                    className={({ isActive }) => cn("flex min-h-[44px] items-center gap-3 rounded-xl px-3 font-medium transition", isActive ? "rs-active bg-accent text-[color:var(--on-accent)] shadow-soft ring-glow" : "text-ink hover:bg-[var(--surface-2)]", collapsed && !mobile && "justify-center px-0")}>
                    {it.icon}
                    {(!collapsed || mobile) && <span className="flex-1 truncate">{t(`nav.${it.key}`)}</span>}
                    {(!collapsed || mobile) && !!it.badge && <span className="rounded-full bg-danger px-2 text-xs font-bold text-white">{it.badge}</span>}
                  </NavLink>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </nav>
      <div className="border-t border-line p-3">
        <div className={cn("flex items-center gap-3 rounded-xl p-2", collapsed && !mobile && "justify-center")}>
          <div className="grid h-10 w-10 shrink-0 place-items-center rounded-full bg-accent-soft font-bold">{user.name.slice(0, 1).toUpperCase()}</div>
          {(!collapsed || mobile) && <div className="min-w-0 flex-1"><p className="truncate font-semibold">{user.name}</p><p className="text-xs text-muted">{t(`roles.${user.role}`)}</p></div>}
        </div>
        <button className={cn("btn-ghost mt-1 w-full justify-start gap-3", collapsed && !mobile && "justify-center")} data-testid="logout"
          onClick={() => { logout(); qc.clear(); nav("/"); }}>
          <LogOut className="h-5 w-5" />{(!collapsed || mobile) && t("nav.logout")}
        </button>
      </div>
    </aside>
  );

  return (
    <div className="flex h-full">
      <a href="#main" className="sr-only focus:not-sr-only focus:absolute focus:left-2 focus:top-2 focus:z-[200] focus:rounded-xl focus:bg-white focus:p-3">{t("a11y.skip")}</a>
      <div className="hidden lg:block no-print">{sidebar(false)}</div>
      {drawer && (
        <div className="fixed inset-0 z-[70] lg:hidden">
          <div className="absolute inset-0 bg-slate-900/40" onClick={() => setDrawer(false)} />
          <div className="absolute inset-y-0 left-0 animate-fadeUp">{sidebar(true)}</div>
        </div>
      )}
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="no-print sticky top-0 z-40 flex h-16 items-center gap-1 border-b border-line glass px-3 sm:px-5">
          <button className="btn-ghost !px-3 lg:hidden" onClick={() => setDrawer(true)} aria-label={t("a11y.menu")}><Menu className="h-5 w-5" /></button>
          <div className="flex-1" />
          {(user.role === "patient" || user.role === "caregiver") && (
            <Link to="/kidney" className="mr-1 hidden items-center gap-2 rounded-xl px-2 py-1 hover:bg-[var(--surface-2)] sm:flex" aria-label={t("nav.livingKidney")}>
              <MiniKidney state={kidney} size={20} />
              {kidney?.has_data && <span className="text-sm font-semibold">{t(`stages.${kidney.stage_name}`)}</span>}
            </Link>
          )}
          {user.role !== "admin" && <button className="inline-flex min-h-[40px] items-center gap-2 rounded-xl px-3 text-sm font-bold text-white shadow-soft" style={{ background: "#16a34a" }} onClick={() => setQs(true)} data-testid="quick-whatsapp"><MessageCircle className="h-4 w-4" /><span className="hidden sm:inline">Send on WhatsApp</span></button>}
          <TopBarActions />
          <A11yMenu />
          <NotificationBell />
        </header>
        <main id="main" style={{ "--stick": "0px" } as React.CSSProperties} className="flex-1 overflow-y-auto px-4 py-6 sm:px-6 lg:px-8">
          <div className="mx-auto w-full max-w-[1200px]"><Outlet /></div>
        </main>
      </div>
      {qs && <QuickSend open={qs} onClose={() => setQs(false)} />}
      <Toasts />
    </div>
  );
}

/** Minimal top bar for public pages (landing, auth, public pulse). */
export function PublicBar({ children }: { children?: ReactNode }) {
  const { t } = useTranslation();
  const user = useSession((s) => s.user);
  return (
    <header className="sticky top-0 z-40 flex h-16 items-center gap-2 border-b border-line glass px-4 sm:px-8">
      <Link to="/" className="flex flex-1 items-center gap-2 text-lg font-bold">
        <span className="grid h-9 w-9 place-items-center rounded-xl bg-accent-soft"><MiniKidney state={null} size={16} /></span>{t("app.name")}
      </Link>
      {children}
      <TopBarActions />
      {user ? <Link to="/home" className="btn-primary">{t("nav.home")}</Link> : <Link to="/login" className="btn-soft">{t("auth.signIn")}</Link>}
    </header>
  );
}
