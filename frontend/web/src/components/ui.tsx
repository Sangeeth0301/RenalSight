import * as Dialog from "@radix-ui/react-dialog";
import { AlertTriangle, CheckCircle2, Info, Loader2, X } from "lucide-react";
import { useEffect, useRef, useState, type ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { ApiError } from "@/lib/api";
import { cn, errorMessage } from "@/lib/utils";
import { useSession } from "@/store/session";

// ---------------------------------------------------------------- toasts + error helper
export function useNotify() {
  const { t } = useTranslation();
  const toast = useSession((s) => s.toast);
  return {
    ok: (text: string) => toast("ok", text),
    info: (text: string) => toast("info", text),
    error: (e: unknown) => toast("error", errorMessage(e, t)),
    errorText: (text: string) => toast("error", text),
  };
}

export function Toasts() {
  const toasts = useSession((s) => s.toasts);
  const dismiss = useSession((s) => s.dismissToast);
  return (
    <div className="fixed bottom-4 right-4 z-[100] flex w-[min(92vw,380px)] flex-col gap-2" aria-live="polite" role="status">
      {toasts.map((t) => (
        <div key={t.id} className={cn("card flex items-start gap-3 p-3 animate-fadeUp", t.kind === "error" && "border-danger/50", t.kind === "ok" && "border-ok/50")}>
          {t.kind === "error" ? <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0 text-danger" /> : t.kind === "ok" ? <CheckCircle2 className="mt-0.5 h-5 w-5 shrink-0 text-ok" /> : <Info className="mt-0.5 h-5 w-5 shrink-0 text-info" />}
          <p className="flex-1 text-sm">{t.text}</p>
          <button aria-label="close" className="text-muted hover:text-ink" onClick={() => dismiss(t.id)}><X className="h-4 w-4" /></button>
        </div>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------- layout bits
export function PageHeader({ title, subtitle, right, chip }: { title: string; subtitle?: string; right?: ReactNode; chip?: ReactNode }) {
  return (
    <div className="mb-5 flex flex-wrap items-start justify-between gap-3">
      <div>
        <h1 className="flex flex-wrap items-center gap-2 text-2xl font-bold tracking-tight sm:text-3xl">{title}{chip}</h1>
        {subtitle && <p className="mt-1 max-w-3xl text-muted">{subtitle}</p>}
      </div>
      {right}
    </div>
  );
}

export function Card({ className, children, ...rest }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("card p-4 sm:p-5", className)} {...rest}>{children}</div>;
}

export function Chip({ children, tone = "slate", className }: { children: ReactNode; tone?: "slate" | "ok" | "warn" | "danger" | "info" | "accent"; className?: string }) {
  const tones = {
    slate: "bg-slate-100 text-slate-700", ok: "bg-emerald-100 text-emerald-800", warn: "bg-amber-100 text-amber-800",
    danger: "bg-rose-100 text-rose-800", info: "bg-blue-100 text-blue-800", accent: "bg-accent-soft text-ink",
  } as const;
  return <span className={cn("chip", tones[tone], className)}>{children}</span>;
}

export function DemoBadge() {
  const { t } = useTranslation();
  return <Chip tone="warn">{t("app.demoBadge")}</Chip>;
}
export function EstimateChip() {
  const { t } = useTranslation();
  return <Chip tone="info">{t("app.estimate")}</Chip>;
}

export function Spinner({ className }: { className?: string }) {
  return <Loader2 className={cn("h-5 w-5 animate-spin text-accent", className)} aria-hidden />;
}

export function Skeleton({ className }: { className?: string }) {
  return <div className={cn("skeleton", className)} aria-hidden />;
}

export function LoadingBlock({ rows = 3 }: { rows?: number }) {
  const { t } = useTranslation();
  return (
    <div className="space-y-3" role="status" aria-label={t("app.loading")}>
      {Array.from({ length: rows }).map((_, i) => <Skeleton key={i} className="h-16 w-full" />)}
    </div>
  );
}

export function EmptyState({ title, body, action, icon }: { title: string; body?: string; action?: ReactNode; icon?: ReactNode }) {
  return (
    <div className="flex flex-col items-center gap-3 rounded-xl2 border border-dashed border-line bg-white/60 px-6 py-10 text-center">
      <div className="grid h-14 w-14 place-items-center rounded-full bg-accent-soft text-accent">{icon ?? <Info className="h-7 w-7" />}</div>
      <p className="text-lg font-semibold">{title}</p>
      {body && <p className="max-w-md text-muted">{body}</p>}
      {action}
    </div>
  );
}

export function ErrorState({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  const { t } = useTranslation();
  return (
    <div className="flex flex-col items-center gap-3 rounded-xl2 border border-rose-200 bg-rose-50 px-6 py-8 text-center">
      <AlertTriangle className="h-8 w-8 text-danger" />
      <p className="font-medium">{errorMessage(error, t)}</p>
      {onRetry && <button className="btn-outline" onClick={onRetry}>{t("app.retry")}</button>}
    </div>
  );
}

export function Disclaimer({ className }: { className?: string }) {
  const { t } = useTranslation();
  return <p className={cn("mt-6 text-center text-xs text-muted", className)}>{t("app.disclaimer")}</p>;
}

/** Sticky rose banner when the kidney state is urgent (global safety rule 4). */
export function UrgentBanner({ children }: { children?: ReactNode }) {
  const { t } = useTranslation();
  return (
    <div className="sticky top-[var(--stick,0px)] z-30 mb-4 flex flex-wrap items-center gap-3 rounded-xl2 border border-rose-300 bg-rose-50 p-3 text-rose-900 shadow-soft" role="alert">
      <AlertTriangle className="h-5 w-5 shrink-0" />
      <p className="flex-1 font-semibold">{t("kidney.urgentBanner")}</p>
      {children}
    </div>
  );
}

// ---------------------------------------------------------------- form bits
export function Field({ label, hint, error, children, htmlFor }: { label: string; hint?: string; error?: string; children: ReactNode; htmlFor?: string }) {
  return (
    <div>
      <label className="label" htmlFor={htmlFor}>{label}</label>
      {children}
      {hint && !error && <p className="mt-1 text-xs text-muted">{hint}</p>}
      {error && <p className="mt-1 text-xs font-medium text-danger">{error}</p>}
    </div>
  );
}

export function Segmented<T extends string>({ value, onChange, options, className }: { value: T; onChange: (v: T) => void; options: { value: T; label: ReactNode }[]; className?: string }) {
  return (
    <div className={cn("inline-flex flex-wrap rounded-xl2 border border-line bg-white p-1", className)} role="tablist">
      {options.map((o) => (
        <button key={o.value} role="tab" aria-selected={value === o.value} onClick={() => onChange(o.value)}
          className={cn("min-h-[40px] rounded-xl px-3 text-sm font-semibold transition", value === o.value ? "bg-accent text-white shadow-soft" : "text-ink hover:bg-slate-100")}>
          {o.label}
        </button>
      ))}
    </div>
  );
}

export function Tabs<T extends string>({ value, onChange, tabs }: { value: T; onChange: (v: T) => void; tabs: { value: T; label: ReactNode }[] }) {
  return (
    <div className="mb-4 flex gap-1 overflow-x-auto border-b border-line" role="tablist">
      {tabs.map((tab) => (
        <button key={tab.value} role="tab" aria-selected={value === tab.value} onClick={() => onChange(tab.value)}
          className={cn("whitespace-nowrap border-b-2 px-4 py-3 font-semibold transition", value === tab.value ? "border-accent text-accent" : "border-transparent text-muted hover:text-ink")}>
          {tab.label}
        </button>
      ))}
    </div>
  );
}

export function Progress({ value, max = 100, tone = "accent", className }: { value: number; max?: number; tone?: "accent" | "ok" | "warn" | "danger"; className?: string }) {
  const pct = Math.max(0, Math.min(100, (value / max) * 100));
  const color = { accent: "bg-accent", ok: "bg-ok", warn: "bg-warn", danger: "bg-danger" }[tone];
  return (
    <div className={cn("h-2.5 w-full overflow-hidden rounded-full bg-slate-100", className)} role="progressbar" aria-valuenow={Math.round(pct)} aria-valuemin={0} aria-valuemax={100}>
      <div className={cn("h-full rounded-full transition-all duration-700", color)} style={{ width: `${pct}%` }} />
    </div>
  );
}

export function SeverityMeter({ value }: { value: number }) {
  const v = Math.max(0, Math.min(100, value));
  return (
    <div className="relative h-3 w-full overflow-hidden rounded-full" style={{ background: "linear-gradient(90deg,#10b981 0%,#f59e0b 55%,#e11d48 100%)" }} role="meter" aria-valuenow={Math.round(v)} aria-valuemin={0} aria-valuemax={100}>
      <div className="absolute inset-y-0 right-0 bg-slate-100/85 transition-all duration-700" style={{ width: `${100 - v}%` }} />
      <div className="absolute top-1/2 h-5 w-1.5 -translate-y-1/2 rounded bg-ink shadow transition-all duration-700" style={{ left: `calc(${v}% - 3px)` }} />
    </div>
  );
}

// ---------------------------------------------------------------- dialog
export function Modal({ open, onClose, title, children, wide, description }: { open: boolean; onClose: () => void; title: string; children: ReactNode; wide?: boolean; description?: string }) {
  return (
    <Dialog.Root open={open} onOpenChange={(o) => !o && onClose()}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-[90] bg-slate-900/40 backdrop-blur-[2px]" />
        <Dialog.Content className={cn("card fixed left-1/2 top-1/2 z-[95] max-h-[90vh] w-[min(94vw,520px)] -translate-x-1/2 -translate-y-1/2 overflow-y-auto p-5 shadow-lift", wide && "w-[min(94vw,760px)]")}>
          <div className="mb-3 flex items-start justify-between gap-3">
            <Dialog.Title className="text-xl font-bold">{title}</Dialog.Title>
            <Dialog.Close className="rounded-full p-1.5 text-muted hover:bg-slate-100" aria-label="close"><X className="h-5 w-5" /></Dialog.Close>
          </div>
          <Dialog.Description className={description ? "mb-3 text-sm text-muted" : "sr-only"}>{description ?? title}</Dialog.Description>
          {children}
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}

// ---------------------------------------------------------------- misc hooks
export function useInterval(fn: () => void, ms: number | null) {
  const ref = useRef(fn);
  ref.current = fn;
  useEffect(() => {
    if (ms === null) return;
    const id = setInterval(() => { if (!document.hidden) ref.current(); }, ms);
    return () => clearInterval(id);
  }, [ms]);
}

export function useDebounced<T>(value: T, ms = 300): T {
  const [v, setV] = useState(value);
  useEffect(() => { const id = setTimeout(() => setV(value), ms); return () => clearTimeout(id); }, [value, ms]);
  return v;
}

export function apiErrorStatus(e: unknown) { return e instanceof ApiError ? e.status : -1; }
