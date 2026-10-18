import { useMutation, useQuery } from "@tanstack/react-query";
import { Bot, Info, Send, X } from "lucide-react";
import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, useSearchParams } from "react-router-dom";
import { Bar, BarChart, CartesianGrid, ComposedChart, Legend, Line, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Card, Chip, DemoBadge, ErrorState, EstimateChip, LoadingBlock, Modal, PageHeader, Segmented, Spinner, useDebounced, useNotify } from "@/components/ui";
import { api } from "@/lib/api";
import { currentLang } from "@/i18n";
import { cn, fmtMillions, fmtNumber, stageColor, tx } from "@/lib/utils";
import { useSession } from "@/store/session";

const STAGES = ["G1", "G2", "G3a", "G3b", "G4", "G5"] as const;
const SCEN = ["current_trend", "faster_decline", "rising"] as const;
const INDICATIVE = new Set(["nephrologists_needed", "stage5_people", "dialysis_patients", "dialysis_sessions_per_year", "dialysis_stations_needed", "nephrology_visits_per_year"]);

export default function Pulse() {
  const { t, i18n } = useTranslation();
  const user = useSession((s) => s.user);
  const [sp, setSp] = useSearchParams();
  const region = sp.get("region") ?? "IND";
  const year = Number(sp.get("year") ?? 2035);
  const scenario = (sp.get("scenario") ?? "current_trend") as (typeof SCEN)[number];
  const [advanced, setAdvanced] = useState(false);
  const [dial, setDial] = useState<number | null>(null);
  const [drawer, setDrawer] = useState(false);
  const [analyst, setAnalyst] = useState(false);
  const set = (k: string, v: string) => { const n = new URLSearchParams(sp); n.set(k, v); setSp(n, { replace: true }); };

  const regionsQ = useQuery({ queryKey: ["pop", "regions"], queryFn: () => api.popRegions(), staleTime: 3600_000 });
  const presets = regionsQ.data?.presets;
  const change = presets?.[scenario]?.annual_change_pct;
  const dYear = useDebounced(year, 250);
  const common = { annual_change_pct: change, dialysis_fraction: dial ?? undefined };
  const est = useQuery({ queryKey: ["pop", "est", region, dYear, change, dial], queryFn: () => api.popEstimate({ region, year: dYear, ...common }), enabled: !!presets, placeholderData: (p) => p });
  const series = useQuery({ queryKey: ["pop", "series", region, change, dial], queryFn: () => api.popSeries({ region, start: 2020, end: 2050, ...common }), enabled: !!presets });
  const cmp = useQuery({ queryKey: ["pop", "cmp", region, dYear, dial], queryFn: () => api.popCompare({ region, year: dYear, dialysis_fraction: dial ?? undefined }), enabled: !!presets });
  const map = useQuery({ queryKey: ["pop", "map", dYear, change], queryFn: () => api.popMap({ year: dYear, annual_change_pct: change }), enabled: !!presets });

  const e = est.data;
  const stageData = useMemo(() => (e ? STAGES.map((s) => ({ s, v: e.stages[s] })) : []), [e]);
  const maxCases = Math.max(...(map.data?.regions.map((r) => r.ckd_cases) ?? [1]));

  if (regionsQ.isLoading) return <LoadingBlock rows={4} />;
  if (regionsQ.error) return <ErrorState error={regionsQ.error} onRetry={() => regionsQ.refetch()} />;

  return (
    <>
      <PageHeader title={t("pulse.title")} subtitle={t("pulse.subtitle")} chip={<EstimateChip />} right={<button className="btn-soft" onClick={() => (user ? setAnalyst(true) : null)} disabled={!user} data-testid="open-analyst"><Bot className="h-4 w-4" />{user ? t("pulse.askAnalyst") : <Link to="/login">{t("auth.signIn")}</Link>}</button>} />

      <div className="sticky top-[var(--stick,0px)] z-30 -mx-1 mb-4 rounded-xl2 border border-line bg-white/95 p-3 shadow-soft backdrop-blur">
        <div className="flex flex-wrap items-center gap-3">
          <div className="flex flex-wrap gap-1" data-testid="region-chips">{regionsQ.data?.regions.map((r) => <button key={r.code} onClick={() => set("region", r.code)} data-testid={`region-${r.code}`} className={cn("chip !px-3 !py-1.5 text-sm", region === r.code ? "bg-accent text-white" : "bg-slate-100 hover:bg-accent-soft")}>{r.name}</button>)}</div>
          <div className="flex min-w-[220px] flex-1 items-center gap-3"><span className="text-sm font-semibold">{t("pulse.year")}</span>
            <input type="range" min={2020} max={2050} value={year} onChange={(ev) => set("year", ev.target.value)} className="flex-1 accent-[var(--accent)]" data-testid="year" aria-label={t("pulse.year")} />
            <b className="w-12 text-center" data-testid="year-value">{year}</b>{year > 2023 ? <Chip tone="info">{t("app.estimate")}</Chip> : <Chip>{year === 2023 ? "anchor" : "model"}</Chip>}</div>
          <Segmented value={scenario} onChange={(v) => set("scenario", v)} options={SCEN.map((s) => ({ value: s, label: t(`pulse.scenarios.${s}`).split("(")[0] }))} />
          <button className="btn-ghost text-sm" onClick={() => setAdvanced(!advanced)}>⚙</button>
        </div>
        {advanced && <div className="mt-3 flex flex-wrap items-center gap-4 border-t border-line pt-3 text-sm"><label className="flex items-center gap-2">{t("pulse.needsList.dialysis_patients")}: <b>{Math.round((dial ?? regionsQ.data?.defaults.dialysis_fraction_of_stage5 ?? 0.5) * 100)}%</b>
          <input type="range" min={0} max={1} step={0.05} value={dial ?? regionsQ.data?.defaults.dialysis_fraction_of_stage5 ?? 0.5} onChange={(ev) => setDial(Number(ev.target.value))} className="accent-[var(--accent)]" /></label>
          <span className="text-muted">{tx(t, "pulse.scenarios." + scenario)}</span></div>}
      </div>

      {!e ? <LoadingBlock rows={3} /> : (
        <div className="space-y-6">
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4" data-testid="headline">
            <Card><p className="text-sm text-muted">{t("pulse.cases")}</p><p className="text-3xl font-extrabold" data-testid="cases">{fmtMillions(e.ckd_cases, i18n.language)}</p><p className="text-xs text-muted">{e.region_name} · {e.year}</p></Card>
            <Card><p className="text-sm text-muted">{t("pulse.highAlt")}</p><p className="text-3xl font-extrabold">{fmtMillions(e.ckd_cases_high_alt, i18n.language)}</p><p className="text-xs text-muted">{fmtNumber(e.prevalence_pct_high_alt, i18n.language)}%</p></Card>
            <Card><p className="text-sm text-muted">{t("pulse.prevalence")}</p><p className="text-3xl font-extrabold">{fmtNumber(e.prevalence_pct, i18n.language)}%</p></Card>
            <Card><p className="text-sm text-muted">{t("pulse.adults")}</p><p className="text-3xl font-extrabold">{fmtMillions(e.adults, i18n.language)}</p></Card>
          </div>
          <p className="-mt-3 text-sm text-muted">{t("pulse.modelNote")} <button className="font-semibold text-accent underline" onClick={() => setDrawer(true)} data-testid="how">{t("pulse.howCalculated")}</button></p>

          <Card>
            <h2 className="mb-3 text-lg font-bold">{t("pulse.mapNote").length ? t("pulse.region") : ""}</h2>
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6" data-testid="tiles">
              {map.data?.regions.map((r) => {
                const k = r.ckd_cases / maxCases;
                return (
                  <button key={r.region} onClick={() => set("region", r.region)} className={cn("rounded-xl2 border-2 p-3 text-left text-slate-900 transition hover:shadow-lift", region === r.region ? "border-accent" : "border-transparent")}
                    style={{ background: `color-mix(in srgb, #e11d48 ${Math.round(k * 55)}%, #ccfbf1)` }}>
                    <p className="font-bold">{r.name}</p><p className="text-xl font-extrabold">{fmtMillions(r.ckd_cases, i18n.language)}</p><p className="text-xs">{fmtNumber(r.prevalence_pct, i18n.language)}%</p>
                    {r.reported_mortality_per_lakh_2023 !== null && <p className="mt-1 text-[11px]">{r.reported_mortality_per_lakh_2023} {t("pulse.perLakh")}</p>}
                  </button>
                );
              })}
            </div>
            <p className="mt-2 text-xs text-muted">{t("pulse.mapNote")}</p>
          </Card>

          <div className="grid gap-6 lg:grid-cols-2">
            <Card><h2 className="mb-3 flex items-center gap-2 text-lg font-bold">{t("pulse.stageSplit")} <Chip tone="slate">{t("pulse.indicative")}</Chip></h2>
              <div className="space-y-2" data-testid="stages">{stageData.map((s) => <div key={s.s}><div className="flex justify-between text-sm"><span>{t(`gStage.${s.s}`)}</span><b>{fmtMillions(s.v, i18n.language)}</b></div><div className="h-3 rounded-full bg-slate-100"><div className="h-3 rounded-full" style={{ width: `${Math.max(1, (s.v / e.ckd_cases) * 100)}%`, background: stageColor(s.s) }} /></div></div>)}</div></Card>
            <Card><h2 className="mb-3 text-lg font-bold">{t("pulse.byAge")}</h2>
              <div className="h-60"><ResponsiveContainer><BarChart data={e.by_age} margin={{ left: -10, right: 8 }}><CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" /><XAxis dataKey="age_group" tick={{ fontSize: 10 }} /><YAxis tickFormatter={(v) => fmtMillions(v, i18n.language)} tick={{ fontSize: 11 }} /><Tooltip formatter={(v: any) => fmtMillions(Number(v), i18n.language)} /><Bar dataKey="cases" fill="var(--accent)" radius={[6, 6, 0, 0]} /></BarChart></ResponsiveContainer></div></Card>
          </div>

          <Card>
            <h2 className="mb-3 text-lg font-bold">{t("pulse.needs")}</h2>
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4" data-testid="needs">
              {Object.entries(e.needs).map(([k, v]) => (
                <div key={k} className="rounded-xl2 border border-line p-3"><p className="text-sm text-muted">{t(`pulse.needsList.${k}`, { defaultValue: k })}</p><p className="text-2xl font-extrabold">{fmtMillions(v, i18n.language)}</p>{INDICATIVE.has(k) && <Chip tone="warn" className="mt-1">{t("pulse.indicative")}</Chip>}</div>
              ))}
            </div>
            <h3 className="mb-2 mt-5 font-bold">{t("pulse.gap")}</h3>
            {!e.capacity_gap ? <p className="text-muted" data-testid="no-capacity">{t("pulse.noCapacity")}</p> : (
              <div className="grid gap-3 sm:grid-cols-2" data-testid="gap">
                {(["dialysis_stations", "nephrologists"] as const).map((k) => { const g = e.capacity_gap![k]; return g && (
                  <div key={k} className="rounded-xl2 border border-line p-3"><p className="font-semibold">{t(`pulse.needsList.${k === "dialysis_stations" ? "dialysis_stations_needed" : "nephrologists_needed"}`)}</p>
                    <div className="mt-1 grid grid-cols-3 text-center"><div><p className="text-xs text-muted">{t("pulse.have")}</p><b>{fmtNumber(g.have, i18n.language, { maximumFractionDigits: 0 })}</b></div><div><p className="text-xs text-muted">{t("pulse.need")}</p><b>{fmtNumber(g.need, i18n.language, { maximumFractionDigits: 0 })}</b></div><div><p className="text-xs text-muted">{t("pulse.missing")}</p><b className={g.gap > 0 ? "text-danger" : "text-ok"}>{fmtNumber(g.gap, i18n.language, { maximumFractionDigits: 0 })}</b></div></div></div>); })}
                <p className="text-xs text-muted sm:col-span-2">{e.capacity_gap.source}</p>
              </div>
            )}
          </Card>

          <div className="grid gap-6 lg:grid-cols-2">
            <Card><h2 className="mb-3 text-lg font-bold">{t("pulse.trend")}</h2>
              <div className="h-64" data-testid="trend"><ResponsiveContainer><ComposedChart data={series.data?.series ?? []} margin={{ left: -4, right: 8 }}><CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" /><XAxis dataKey="year" tick={{ fontSize: 11 }} /><YAxis tickFormatter={(v) => fmtMillions(v, i18n.language)} tick={{ fontSize: 11 }} /><Tooltip formatter={(v: any) => fmtMillions(Number(v), i18n.language)} /><Legend />
                <ReferenceLine x={2023} stroke="#94a3b8" strokeDasharray="4 4" label={{ value: "2023", fontSize: 11 }} /><ReferenceLine x={year} stroke="var(--accent)" strokeWidth={2} />
                <Line dataKey="ckd_cases" name={t("pulse.cases")} stroke="var(--accent)" strokeWidth={3} dot={false} /><Line dataKey="ckd_cases_high_alt" name={t("pulse.highAlt")} stroke="#94a3b8" strokeDasharray="6 4" dot={false} /></ComposedChart></ResponsiveContainer></div></Card>
            <Card><h2 className="mb-3 text-lg font-bold">{t("pulse.compare")}</h2>
              <div className="space-y-3" data-testid="compare">{cmp.data?.scenarios.map((s) => <div key={s.scenario}><div className="flex justify-between text-sm"><span>{t(`pulse.scenarios.${s.scenario}`)}</span><b>{fmtMillions(s.ckd_cases, i18n.language)} <span className={s.cases_vs_current_trend > 0 ? "text-danger" : s.cases_vs_current_trend < 0 ? "text-ok" : "text-muted"}>({s.cases_vs_current_trend > 0 ? "+" : ""}{fmtMillions(s.cases_vs_current_trend, i18n.language)})</span></b></div>
                <div className="h-3 rounded-full bg-slate-100"><div className="h-3 rounded-full bg-accent" style={{ width: `${(s.ckd_cases / Math.max(...cmp.data!.scenarios.map((x) => x.ckd_cases))) * 100}%` }} /></div></div>)}
                <p className="text-xs text-muted">{cmp.data?.note}</p></div></Card>
          </div>
        </div>
      )}

      <Modal open={drawer} onClose={() => setDrawer(false)} title={t("pulse.howCalculated")} wide>
        {e && <div className="space-y-4 text-sm">
          <section><h3 className="font-bold">{t("pulse.assumptions")}</h3><ul className="mt-1 list-disc space-y-1 pl-5">{e.assumptions.map((a) => <li key={a}>{a}</li>)}</ul></section>
          <section><h3 className="font-bold">{t("pulse.sources")}</h3><ul className="mt-1 list-disc space-y-1 pl-5">{e.sources.map((a) => <li key={a}>{a}</li>)}</ul></section>
          <section><h3 className="font-bold">{t("pulse.limits")}</h3><p className="mt-1">{e.limitations}</p></section>
          <SourcesStatus />
        </div>}
      </Modal>
      {user && <AnalystPanel open={analyst} onClose={() => setAnalyst(false)} onApply={(r, y) => { const n = new URLSearchParams(sp); if (r) n.set("region", r); if (y) n.set("year", String(y)); setSp(n, { replace: true }); }} />}
    </>
  );
}

function SourcesStatus() {
  const q = useQuery({ queryKey: ["pop", "sources"], queryFn: () => api.popSources() });
  if (!q.data) return null;
  return (
    <section><h3 className="font-bold">Verification status</h3>
      <ul className="mt-1 space-y-1">{Object.entries(q.data).map(([k, v]: [string, any]) => <li key={k} className="rounded-lg bg-slate-50 p-2"><b>{k}</b>{v.status || v._status ? <span className="text-muted"> — {v.status ?? v._status}</span> : null}</li>)}</ul></section>
  );
}

function AnalystPanel({ open, onClose, onApply }: { open: boolean; onClose: () => void; onApply: (region?: string, year?: number) => void }) {
  const { t } = useTranslation();
  const notify = useNotify();
  const [text, setText] = useState("");
  const [log, setLog] = useState<{ role: "user" | "bot"; text: string; tools?: string[]; basic?: boolean }[]>([]);
  const m = useMutation({
    mutationFn: (q: string) => api.analystChat(q, currentLang()),
    onSuccess: (r) => {
      setLog((p) => [...p, { role: "bot", text: r.reply, tools: r.tools_used.map((x) => x.tool), basic: r.provider === "rules" }]);
      const reg: Record<string, string> = { "tamil nadu": "IN-TN", "west bengal": "IN-WB", "andhra": "IN-AP", "telangana": "IN-TG", "karnataka": "IN-KA", "india": "IND" };
      const low = r.reply.toLowerCase();
      const found = Object.keys(reg).find((k) => low.includes(k));
      const yr = r.reply.match(/\b(20[2-5]\d)\b/);
      if (found || yr) onApply(found ? reg[found] : undefined, yr ? Number(yr[1]) : undefined);
    },
    onError: (e) => notify.error(e),
  });
  const send = () => { const q = text.trim(); if (!q) return; setLog((p) => [...p, { role: "user", text: q }]); setText(""); m.mutate(q); };
  if (!open) return null;
  return (
    <div className="card fixed bottom-4 right-4 z-[60] flex h-[min(70vh,560px)] w-[min(94vw,400px)] flex-col overflow-hidden shadow-lift" data-testid="analyst">
      <div className="flex items-center gap-2 border-b border-line bg-accent-soft px-4 py-3"><Bot className="h-5 w-5 text-accent" /><p className="flex-1 font-bold">{t("pulse.askAnalyst")}</p><button onClick={onClose} aria-label="close"><X className="h-5 w-5" /></button></div>
      <div className="flex-1 space-y-2 overflow-y-auto bg-slate-50 p-3">
        {log.length === 0 && <p className="flex gap-2 text-sm text-muted"><Info className="h-4 w-4 shrink-0" />{t("pulse.analystPlaceholder")}</p>}
        {log.map((l, i) => <div key={i} className={cn("max-w-[92%] rounded-2xl px-3 py-2 text-sm", l.role === "user" ? "ml-auto bg-accent text-white" : "border border-line bg-white")} data-testid={l.role === "bot" ? "analyst-reply" : undefined}><p className="whitespace-pre-wrap">{l.text}</p>{l.basic && <p className="mt-1 text-xs text-muted">{t("app.basicMode")}</p>}{l.tools && l.tools.length > 0 && <p className="mt-1 text-[11px] text-muted">{l.tools.join(", ")}</p>}</div>)}
        {m.isPending && <p className="animate-pulse text-sm text-muted">{t("buddy.thinking")}</p>}
      </div>
      <div className="flex gap-2 border-t border-line p-2"><input className="input" data-testid="analyst-input" placeholder={t("pulse.analystPlaceholder")} value={text} onChange={(e) => setText(e.target.value)} onKeyDown={(e) => e.key === "Enter" && send()} maxLength={1000} />
        <button className="btn-primary !px-3" onClick={send} disabled={m.isPending} aria-label={t("app.send")} data-testid="analyst-send">{m.isPending ? <Spinner className="text-white" /> : <Send className="h-5 w-5" />}</button></div>
    </div>
  );
}

export { DemoBadge };
