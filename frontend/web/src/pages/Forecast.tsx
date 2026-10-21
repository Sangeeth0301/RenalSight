import { useQuery } from "@tanstack/react-query";
import { Activity, ArrowRight, CalendarClock, ChevronDown, HeartHandshake, Info, Pill, ShieldCheck, Stethoscope } from "lucide-react";
import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import { Area, AreaChart, CartesianGrid, ComposedChart, Line, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { LivingKidney, NO_STATE } from "@/components/LivingKidney";
import { Card, Chip, Disclaimer, EmptyState, ErrorState, EstimateChip, LoadingBlock, PageHeader, Segmented, useDebounced } from "@/components/ui";
import { api, ApiError, type Journey, type JourneyMilestone, type JourneyRun } from "@/lib/api";
import { cn, latest, stageColor } from "@/lib/utils";
import { useSession } from "@/store/session";

type Which = "current" | "with_levers";
const LEVER_ORDER = ["bp_control", "sugar_control", "protein_drug", "sglt2"] as const;
const THRESH = [60, 45, 30, 20, 15, 10];
const OUT_COLORS = { ok: "#10b981", kidney_failure: "#f59e0b", died_before_kf: "#64748b", died_after_kf: "#334155" };

function applies(key: string, j: Journey): boolean {
  const i = j.inputs;
  if (key === "bp_control") return (i.sbp ?? 0) > 130;
  if (key === "sugar_control") return i.diabetes && (i.hba1c ?? 0) > 7;
  if (key === "protein_drug") return (i.acr ?? 0) >= 30;
  return j.egfr_now >= 20;
}

function cell(m: JourneyMilestone, today: number, horizon: number, t: (k: string, d: string, o?: Record<string, unknown>) => string): { main: string; sub?: string; tone: "done" | "soon" | "later" | "none" } {
  if (m.already) return { main: t("journey.alreadyReached", "Already reached"), tone: "done" };
  if (m.median !== null) {
    return { main: `${m.median_year}`, sub: t("journey.cellSub", "age {{age}} · range {{from}} to {{to}}", { age: m.median_age, from: m.fast_year ?? "", to: m.slow_year ?? t("journey.later", "later") }), tone: (m.median ?? 99) <= 5 ? "soon" : "later" };
  }
  return { main: t("journey.notBy", "Not expected by {{y}}", { y: today + horizon }), sub: t("journey.chanceOf", "{{p}}% chance", { p: Math.round(m.chance_within_horizon * 100) }), tone: "none" };
}

export default function Forecast() {
  const { t } = useTranslation();
  const tt = t as unknown as (k: string, d: string, o?: Record<string, unknown>) => string;
  const user = useSession((s) => s.user)!;
  const [picked, setPicked] = useState<string[] | null>(null);
  const [which, setWhich] = useState<Which>("current");
  const [year, setYear] = useState(0);
  const [horizon, setHorizon] = useState(15);
  const [open, setOpen] = useState(false);

  const labsQ = useQuery({ queryKey: ["labs"], queryFn: () => api.labs() });
  const dLevers = useDebounced(picked, 350);
  const jq = useQuery({ queryKey: ["journey", dLevers?.join(",") ?? "default", horizon], queryFn: () => api.myJourney(dLevers ?? [], horizon), retry: false, placeholderData: (p) => p });
  const j = jq.data as Journey | undefined;
  const labs = labsQ.data ?? [];
  const cur = { acr: latest(labs, "acr"), sbp: latest(labs, "sbp"), hgb: latest(labs, "hgb"), potassium: latest(labs, "potassium") };

  const run: JourneyRun | undefined = j && j.has_data !== false ? j[which] : undefined;
  const idx = run ? Math.min(Math.round(year / 0.25), run.bands.p50.length - 1) : 0;
  const egfrAt = run ? run.bands.p50[idx] : undefined;
  const dK = useDebounced({ egfr: egfrAt, ...cur }, 250);
  const kq = useQuery({
    queryKey: ["kidney-at-year", dK, user.sex], enabled: dK.egfr !== undefined, placeholderData: (p) => p,
    queryFn: () => api.kidneyState({ egfr: dK.egfr!, acr: dK.acr, sbp: dK.sbp, hgb: dK.hgb, potassium: dK.potassium, sex: user.sex ?? undefined }),
  });

  const chart = useMemo(() => {
    if (!j || j.has_data === false) return [];
    const y0 = new Date(j.today).getFullYear();
    const rows = j.current.bands.years.map((y, i) => ({ y, cal: y0 + y, age: Math.round(j.age + y), median: j.current.bands.p50[i], band: [j.current.bands.p10[i], j.current.bands.p90[i]], levers: j.with_levers.bands.p50[i], slow: j.with_levers.bands.p90[i] }));
    const flat = rows.findIndex((r) => r.band[1] <= 3 && r.slow <= 3);                       // every simulated future is at the floor: stop a couple of years later
    return flat < 0 ? rows : rows.slice(0, Math.min(rows.length, flat + 9));
  }, [j]);

  if (labsQ.isLoading || (jq.isLoading && !j)) return <LoadingBlock rows={4} />;
  const noLabs = (jq.error instanceof ApiError && jq.error.status === 422) || (j && j.has_data === false) || (labs.length > 0 && labs.every((l) => l.egfr === null));
  if (noLabs || labs.length === 0) return (<><PageHeader title={tt("forecast.title", "Time machine")} subtitle={tt("forecast.subtitle", "")} /><EmptyState title={tt("forecast.needLabs", "Add a lab report with creatinine to see your journey")} action={<Link to="/reports" className="btn-primary">{tt("labs.add", "Add lab report")}</Link>} /></>);
  if (jq.error || !j || !run) return <ErrorState error={jq.error} onRetry={() => jq.refetch()} />;

  const today = new Date(j.today).getFullYear();
  const used = new Set(j.levers_used);
  const ms = (r: JourneyRun, key: string) => r.milestones.find((m) => m.key === key)!;
  const kf0 = ms(j.current, "g5"), kf1 = ms(j.with_levers, "g5");
  const timelineRow = j.timeline[Math.min(Math.round(year), j.timeline.length - 1)];
  const stageAt = which === "current" ? timelineRow.stage_current : timelineRow.stage_levers;
  const guide = j.stage_guide[stageAt];
  const o = run.outcomes;
  const outData = o ? o.years.map((y, i) => ({ cal: today + y, ok: o.ok[i], kidney_failure: o.kidney_failure[i], died_before_kf: o.died_before_kf[i], died_after_kf: o.died_after_kf[i] })) : [];
  const sv0 = j.current.survival, sv1 = j.with_levers.survival;

  const headline = (m: JourneyMilestone, label: string) => {
    if (m.already) return tt("journey.headIn", "{{label}}: your eGFR is already in the kidney-failure range (below 15). Please stay under a kidney specialist's care.", { label });
    if (m.median !== null) return tt("journey.headMost", "{{label}}: kidney failure range (eGFR below 15) is most likely around {{year}} (age {{age}}), between {{from}} and {{to}}.", { label, year: m.median_year, age: m.median_age, from: m.fast_year, to: m.slow_year ?? tt("journey.later", "later") });
    return tt("journey.headNot", "{{label}}: kidney failure is not expected in the next {{n}} years ({{p}}% chance).", { label, n: j.horizon, p: Math.round(m.chance_within_horizon * 100) });
  };
  const gain = kf0.median !== null && kf1.median !== null && !kf0.already ? Math.round((kf1.median - kf0.median) * 10) / 10 : null;

  const plan = (() => {
    const tx = ms(j.current, "tx_window"), g5 = ms(j.current, "g5"), g4 = ms(j.current, "g4");
    const by = (m: JourneyMilestone) => (m.already ? tt("journey.now", "now") : m.fast_year ? `${tt("journey.by", "by")} ${m.fast_year}` : tt("journey.notSoon", "not needed in this period"));
    return [
      { icon: Stethoscope, title: tt("journey.planNeph", "See a kidney specialist (nephrologist)"), when: g4.already || j.stage_now === "G3b" ? tt("journey.now", "now") : by(g4), to: "/chat" },
      { icon: HeartHandshake, title: tt("journey.planTx", "Transplant evaluation and donor search"), when: by(tx), to: "/hub" },
      { icon: Activity, title: tt("journey.planDial", "Dialysis education and access planning"), when: by(g5), to: "/hub/dialysis" },
      { icon: Pill, title: tt("journey.planCare", "Review medicines and care plan"), when: tt("journey.now", "now"), to: "/care" },
    ];
  })();

  return (
    <div className="space-y-6">
      <PageHeader title={tt("forecast.title", "Time machine")} subtitle={tt("journey.subtitle", "Your kidney journey: how fast it may change, when the big steps may come, and where people like you end up. Estimates, not promises.")} chip={<EstimateChip />}
        right={<div className="flex flex-wrap items-center gap-2"><Segmented value={String(horizon) as "10" | "15" | "20"} onChange={(v) => { setHorizon(Number(v)); setYear(0); }} options={[{ value: "10", label: "10 y" }, { value: "15", label: "15 y" }, { value: "20", label: "20 y" }]} /></div>} />

      <div className="grid gap-6 lg:grid-cols-[340px_minmax(0,1fr)]">
        <Card className="flex flex-col items-center">
          <LivingKidney state={kq.data ?? NO_STATE} size="lg" />
          <p className="mt-3 text-center text-lg font-bold">{timelineRow.year} · {tt("journey.ageShort", "age")} {timelineRow.age}</p>
          <p className="text-sm text-muted">{tt("forecast.slider", "Years from now")}: <b data-testid="year-label">{year}</b> · eGFR ≈ <b>{egfrAt?.toFixed(1)}</b> <span className="ml-1 chip text-white" style={{ background: stageColor(stageAt) }}>{stageAt}</span></p>
          <input data-testid="year-slider" type="range" min={0} max={horizon} step={1} value={year} onChange={(e) => setYear(Number(e.target.value))} className="mt-3 w-full accent-[var(--accent)]" aria-label={tt("forecast.slider", "Years from now")} />
          <div className="mt-3 w-full"><Segmented value={which} onChange={setWhich} className="w-full" options={[{ value: "current", label: tt("journey.today", "Today's care") }, { value: "with_levers", label: tt("journey.withChanges", "With changes") }]} /></div>
        </Card>

        <div className="space-y-6">
          <Card data-testid="journey-headline" className="space-y-3">
            <h2 className="flex items-center gap-2 font-display text-xl font-bold"><CalendarClock className="h-5 w-5 text-accent" />{tt("journey.whenTitle", "When could the kidney reach failure range?")}</h2>
            <p className="text-lg leading-snug"><b>{headline(kf0, tt("journey.ifSame", "If nothing changes"))}</b></p>
            <p className="text-lg leading-snug text-muted">{headline(kf1, tt("journey.withCare", "With the care changes below"))}</p>
            {gain !== null && gain > 0 && <p className="rounded-xl bg-emerald-100 p-3 font-semibold text-emerald-800" data-testid="journey-gain">{tt("journey.gain", "These changes could add about {{n}} years before kidney failure range.", { n: gain })}</p>}
            {j.own_trend_per_year !== null && <p className="text-sm text-muted"><Info className="mr-1 inline h-4 w-4" />{tt("journey.ownTrend", "Your own {{n}} lab results show your eGFR changing by {{v}} per year. That trend is part of the forecast.", { n: j.labs_used, v: j.own_trend_per_year })}</p>}
          </Card>

          <Card data-testid="levers">
            <h2 className="mb-1 flex items-center gap-2 font-display text-lg font-bold"><ShieldCheck className="h-5 w-5 text-accent" />{tt("journey.leversTitle", "What could change the journey?")}</h2>
            <p className="mb-3 text-sm text-muted">{tt("journey.leversBody", "Tick the changes you want to test. Effects are typical trial ranges, shown as estimates. Your doctor decides what is right for you.")}</p>
            <div className="grid gap-2 sm:grid-cols-2">
              {LEVER_ORDER.map((k) => {
                const info = j.levers_info[k], on = (picked ?? j.levers_used).includes(k), ap = applies(k, j);
                return (
                  <label key={k} className={cn("flex cursor-pointer items-start gap-3 rounded-xl border p-3 transition", on ? "border-accent bg-accent-soft" : "border-line", !ap && "opacity-60")}>
                    <input type="checkbox" className="mt-1 h-5 w-5 accent-[var(--accent)]" checked={on} data-testid={`lever-${k}`} onChange={(e) => { const base = picked ?? [...j.levers_used]; setPicked(e.target.checked ? [...new Set([...base, k])] : base.filter((x) => x !== k)); }} />
                    <span><span className="block font-semibold">{tt("journey.lever_" + k, info.label)}</span><span className="block text-xs text-muted">{tt("journey.leverHow_" + k, info.how)}{!ap && ` · ${tt("journey.notNeeded", "does not apply to your current numbers")}`}</span></span>
                  </label>
                );
              })}
            </div>
          </Card>
        </div>
      </div>

      <Card>
        <h2 className="mb-1 font-display text-lg font-bold">{tt("journey.chartTitle", "Kidney function year by year")}</h2>
        <p className="mb-2 text-sm text-muted">{tt("journey.chartBody", "The shaded band holds 8 of 10 simulated futures with today's care. Lines show the middle path. Below 15 is kidney failure range.")}</p>
        <div className="h-80 w-full" data-testid="forecast-chart">
          <ResponsiveContainer>
            <ComposedChart data={chart} margin={{ top: 8, right: 36, left: -8, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="cal" type="number" domain={["dataMin", "dataMax"]} tickCount={8} tick={{ fontSize: 12 }} />
              <YAxis domain={[0, "dataMax + 10"]} tick={{ fontSize: 12 }} />
              <Tooltip formatter={(v: any, n: any) => [Array.isArray(v) ? `${v[0]} to ${v[1]}` : v, n === "band" ? "8 in 10 range" : n === "median" ? "today's care" : "with changes"]} labelFormatter={(l: any) => `${l}`} />
              {THRESH.map((v) => <ReferenceLine key={v} y={v} stroke={v === 15 ? "#e11d48" : "#94a3b8"} strokeDasharray="4 4" label={{ value: String(v), position: "right", fontSize: 11, fill: v === 15 ? "#e11d48" : "#64748b" }} />)}
              <ReferenceLine x={today + year} stroke="var(--accent)" strokeWidth={2} />
              <Area dataKey="band" stroke="none" fill="var(--accent)" fillOpacity={0.16} name="band" />
              <Line dataKey="median" stroke="#e11d48" strokeWidth={3} dot={false} name="median" />
              <Line dataKey="levers" stroke="#10b981" strokeWidth={3} dot={false} strokeDasharray="6 4" name="levers" />
            </ComposedChart>
          </ResponsiveContainer>
        </div>
        <div className="mt-2 flex flex-wrap gap-4 text-xs text-muted"><span><b className="text-[#e11d48]">━</b> {tt("journey.today", "Today's care")}</span><span><b className="text-[#10b981]">┅</b> {tt("journey.withChanges", "With changes")}</span><span>{tt("journey.sliderLine", "Blue line: the year chosen on the slider")}</span></div>
      </Card>

      <Card data-testid="milestones" className="overflow-x-auto">
        <h2 className="mb-1 font-display text-lg font-bold">{tt("journey.milestonesTitle", "Milestones: when and at what age")}</h2>
        <p className="mb-3 text-sm text-muted">{tt("journey.milestonesBody", "Median year with the age you will be, and the range from a fast to a slow decline.")}</p>
        <table className="w-full min-w-[640px] text-sm">
          <thead><tr className="text-left text-xs uppercase text-muted"><th className="py-2">{tt("journey.milestone", "Milestone")}</th><th>{tt("journey.today", "Today's care")}</th><th>{tt("journey.withChanges", "With changes")}</th></tr></thead>
          <tbody>
            {j.current.milestones.map((m, i) => {
              const a = cell(m, today, j.horizon, tt), b = cell(j.with_levers.milestones[i], today, j.horizon, tt);
              const tone = { done: "text-muted", soon: "text-rose-700", later: "text-ink", none: "text-emerald-700" } as const;
              return (
                <tr key={m.key} className="border-t border-[var(--border)]">
                  <td className="py-3 pr-3"><p className="font-semibold">{tt("journey.m_" + m.key, m.label)}</p><p className="text-xs text-muted">{tt("journey.egfrBelow", "eGFR below {{n}}", { n: m.egfr })}</p></td>
                  {[a, b].map((c, k) => <td key={k} className="py-3 pr-3"><p className={cn("text-base font-bold", tone[c.tone])}>{c.main}</p>{c.sub && <p className="text-xs text-muted">{c.sub}</p>}</td>)}
                </tr>
              );
            })}
          </tbody>
        </table>
        <p className="mt-3 text-xs text-muted">{tt("journey.txNote", "Transplant evaluation window (eGFR about 20) and dialysis start (often eGFR 5 to 10, or when symptoms appear) are typical guidance; your doctor decides the timing.")}</p>
      </Card>

      {guide && (
        <Card data-testid="stage-guide">
          <h2 className="mb-1 font-display text-lg font-bold">{tt("journey.atYear", "What this stage is usually like")} <span className="ml-1 chip text-white" style={{ background: stageColor(stageAt) }}>{stageAt}</span> <span className="text-sm font-normal text-muted">· {timelineRow.year}</span></h2>
          <p className="mb-3 text-muted">{tt(`journey.guide_${stageAt}_title`, guide.title)}</p>
          <div className="grid gap-4 md:grid-cols-2">
            <div><p className="mb-1 font-semibold">{tt("journey.happens", "What often happens")}</p><ul className="list-disc space-y-1 pl-5 text-sm">{guide.happens.map((x, i) => <li key={x}>{tt(`journey.guide_${stageAt}_h${i}`, x)}</li>)}</ul></div>
            <div><p className="mb-1 font-semibold">{tt("journey.whatToDo", "What helps")}</p><ul className="list-disc space-y-1 pl-5 text-sm">{guide.do.map((x, i) => <li key={x}>{tt(`journey.guide_${stageAt}_d${i}`, x)}</li>)}</ul></div>
          </div>
        </Card>
      )}

      {o && (
        <Card data-testid="outcomes">
          <h2 className="mb-1 font-display text-lg font-bold">{tt("journey.outTitle", "Where people like you end up")} <Chip tone="info">{which === "current" ? tt("journey.today", "Today's care") : tt("journey.withChanges", "With changes")}</Chip></h2>
          <p className="mb-2 text-sm text-muted">{tt("journey.outBody", "Imagine 100 people with the same age, labs and health as you. This shows how many would be doing well, in kidney failure range, or would have died, year by year. It is a group picture, not a prediction for one person.")}</p>
          <div className="h-64 w-full" data-testid="outcomes-chart">
            <ResponsiveContainer>
              <AreaChart data={outData} stackOffset="expand" margin={{ top: 8, right: 12, left: -10, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="cal" type="number" domain={["dataMin", "dataMax"]} tickCount={6} tick={{ fontSize: 12 }} />
                <YAxis tickFormatter={(v) => `${Math.round(v * 100)}%`} tick={{ fontSize: 12 }} />
                <Tooltip formatter={(v: any) => `${v}%`} />
                <Area dataKey="ok" stackId="1" stroke={OUT_COLORS.ok} fill={OUT_COLORS.ok} name={tt("journey.o_ok", "Kidney still working")} />
                <Area dataKey="kidney_failure" stackId="1" stroke={OUT_COLORS.kidney_failure} fill={OUT_COLORS.kidney_failure} name={tt("journey.o_kf", "Kidney failure range, alive")} />
                <Area dataKey="died_before_kf" stackId="1" stroke={OUT_COLORS.died_before_kf} fill={OUT_COLORS.died_before_kf} name={tt("journey.o_db", "Died before kidney failure")} />
                <Area dataKey="died_after_kf" stackId="1" stroke={OUT_COLORS.died_after_kf} fill={OUT_COLORS.died_after_kf} name={tt("journey.o_da", "Died after kidney failure")} />
              </AreaChart>
            </ResponsiveContainer>
          </div>
          <div className="mt-2 flex flex-wrap gap-3 text-xs">
            {([["ok", "o_ok", "Kidney still working"], ["kidney_failure", "o_kf", "Kidney failure range, alive"], ["died_before_kf", "o_db", "Died before kidney failure"], ["died_after_kf", "o_da", "Died after kidney failure"]] as const).map(([k, key, l]) => <span key={k} className="flex items-center gap-1"><span className="h-3 w-3 rounded-sm" style={{ background: OUT_COLORS[k] }} />{tt("journey." + key, l)}</span>)}
          </div>
          <p className="mt-2 text-xs text-muted">{tt("journey.outNote", "Dialysis or a transplant is not modelled. They change what happens after kidney failure range, so use this as a reason to plan early, not as a verdict.")}</p>
        </Card>
      )}

      {sv0 && sv1 && (
        <Card data-testid="survival">
          <h2 className="mb-1 font-display text-lg font-bold">{tt("journey.survTitle", "Out of 100 people like you, how many are alive")}</h2>
          <p className="mb-3 text-sm text-muted">{tt("journey.survBody", "From a survival model fitted on thousands of US adults. It describes groups, never one person, and it cannot say what will happen to you.")}</p>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            {Object.keys(sv0.at).map((y) => (
              <div key={y} className="rounded-xl border border-line p-3 text-center">
                <p className="text-xs text-muted">{tt("journey.afterYears", "after {{n}} years", { n: y })}</p>
                <p className="font-display text-3xl font-extrabold text-gradient">{Math.round(sv0.at[y])}</p>
                <p className="text-xs text-muted">{tt("journey.withChangesShort", "with changes")}: <b>{Math.round(sv1.at[y])}</b></p>
              </div>
            ))}
          </div>
        </Card>
      )}

      <Card data-testid="plan">
        <h2 className="mb-3 font-display text-lg font-bold">{tt("journey.planTitle", "When to start planning")}</h2>
        <div className="grid gap-3 md:grid-cols-2">
          {plan.map((p) => (
            <Link key={p.title} to={p.to} className="card flex items-center gap-3 p-4">
              <span className="grid h-11 w-11 shrink-0 place-items-center rounded-xl bg-accent-soft text-accent"><p.icon className="h-5 w-5" /></span>
              <span className="min-w-0 flex-1"><span className="block font-semibold">{p.title}</span><span className="text-sm text-muted">{p.when}</span></span>
              <ArrowRight className="h-4 w-4 text-muted" />
            </Link>
          ))}
        </div>
        <p className="mt-2 text-xs text-muted">{tt("journey.planNote", "Dates use the faster end of the range (1 in 10 futures) so that planning starts early enough.")}</p>
      </Card>

      <Card>
        <button className="flex w-full items-center justify-between text-left font-display text-lg font-bold" onClick={() => setOpen(!open)} aria-expanded={open}>{tt("journey.howTitle", "How is this calculated?")}<ChevronDown className={cn("h-5 w-5 transition", open && "rotate-180")} /></button>
        {open && (
          <div className="mt-3 space-y-2 text-sm text-muted">
            <p>{tt("journey.how1", "We simulate 2,500 possible futures. Each starts from your latest eGFR and a yearly decline drawn from your own lab trend (when you have 3 or more results) blended with typical rates for people with your urine protein, blood pressure, diabetes and age.")}</p>
            <p>{tt("journey.how2", "Every future is checked against the milestones above. Where people end up uses a survival model that also looks at each future's own kidney function year by year.")}</p>
            <ul className="list-disc pl-5">{j.assumptions.map((a) => <li key={a}>{a}</li>)}</ul>
          </div>
        )}
      </Card>

      <p className="text-xs text-muted">{j.note}</p>
      <Disclaimer />
    </div>
  );
}
