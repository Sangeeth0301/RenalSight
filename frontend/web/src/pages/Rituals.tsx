import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AnimatePresence, motion } from "framer-motion";
import { AlertTriangle, Check, Droplets, Flame, Moon, Salad, Sun, Sunset } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { MiniKidney } from "@/components/LivingKidney";
import { Card, Disclaimer, ErrorState, LoadingBlock, PageHeader, Progress, UrgentBanner, useNotify } from "@/components/ui";
import { api, type RitualKind, type RitualToday } from "@/lib/api";
import { useMyKidney } from "@/lib/hooks";
import { cn, fmtDate, tx } from "@/lib/utils";

const MEDS: { kind: "med_morning" | "med_noon" | "med_night"; icon: typeof Sun }[] = [
  { kind: "med_morning", icon: Sun }, { kind: "med_noon", icon: Sunset }, { kind: "med_night", icon: Moon },
];
const SYMS = ["swelling", "breathless", "less_urine", "vomiting", "chest_pain", "fatigue", "itching", "cramps"] as const;

export default function Rituals() {
  const { t, i18n } = useTranslation();
  const qc = useQueryClient();
  const notify = useNotify();
  const k = useMyKidney().data;
  const today = useQuery({ queryKey: ["rituals", "today"], queryFn: () => api.ritualsToday() });
  const summary = useQuery({ queryKey: ["rituals", "summary"], queryFn: () => api.ritualsSummary(14) });
  const [sbp, setSbp] = useState("");
  const [dbp, setDbp] = useState("");
  const [sparkle, setSparkle] = useState(0);

  const log = useMutation({
    mutationFn: (b: Parameters<typeof api.ritualLog>[0]) => api.ritualLog(b),
    onSuccess: (r: RitualToday) => { qc.setQueryData(["rituals", "today"], r); void qc.invalidateQueries({ queryKey: ["rituals", "summary"] }); void qc.invalidateQueries({ queryKey: ["care-hub"] }); },
    onError: (e) => notify.error(e),
  });
  const tick = (b: Parameters<typeof api.ritualLog>[0]) => { setSparkle((n) => n + 1); log.mutate(b); };

  if (today.isLoading) return <LoadingBlock rows={4} />;
  if (today.error) return <ErrorState error={today.error} onRetry={() => today.refetch()} />;
  const d = today.data!;
  const e = d.entries;
  const symptoms: string[] = e.symptoms?.items ?? [];
  const glasses: number = e.water?.glasses ?? 0;
  const urgent = d.urgent_symptoms.length > 0 || d.urgent_bp;

  return (
    <>
      {urgent && <UrgentBanner>{d.urgent_symptoms.length > 0 ? <span className="text-sm">{t("rituals.urgent")}</span> : <span className="text-sm">{t("rituals.urgentBp")}</span>}</UrgentBanner>}
      <PageHeader title={t("rituals.title")} subtitle={t("rituals.subtitle")}
        right={<div className="flex flex-wrap items-center gap-3">
          <span className="chip bg-orange-100 !px-3 !py-1.5 text-sm text-orange-800" data-testid="streak"><Flame className="h-4 w-4" />{tx(t, "rituals.streak", { n: d.streak })}</span>
          <div className="w-44"><p className="text-xs text-muted">{t("rituals.adherence")}</p><Progress value={d.medicine_adherence_7d * 100} tone="ok" /></div>
        </div>} />
      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_300px]">
        <div className="space-y-5">
          <Card>
            <div className="mb-3 flex items-center justify-between"><h2 className="text-lg font-bold">{t("rituals.pointsToday")}</h2><b className="text-2xl" data-testid="score">{Math.round(d.score * 100)}%</b></div>
            <Progress value={d.score * 100} tone={d.score >= 0.6 ? "ok" : "warn"} />
          </Card>
          <Card>
            <h2 className="mb-3 text-lg font-bold">{t("rx.medicines")}</h2>
            <div className="grid gap-3 sm:grid-cols-3">
              {MEDS.map(({ kind, icon: Icon }) => {
                const taken = !!e[kind]?.taken;
                return (
                  <button key={kind} data-testid={kind} aria-pressed={taken} onClick={() => tick({ kind, taken: !taken })}
                    className={cn("flex min-h-[96px] flex-col items-center justify-center gap-2 rounded-xl2 border-2 p-3 transition", taken ? "border-ok bg-emerald-50" : "border-line bg-white hover:border-accent")}>
                    <Icon className={cn("h-8 w-8", taken ? "text-ok" : "text-muted")} />
                    <span className="font-semibold">{t(`rituals.${kind}`)}</span>
                    <span className={cn("chip", taken ? "bg-ok text-white" : "bg-slate-100")}>{taken ? <><Check className="h-3 w-3" />{t("rituals.taken")}</> : "—"}</span>
                  </button>
                );
              })}
            </div>
          </Card>
          <div className="grid gap-5 md:grid-cols-2">
            <Card>
              <h2 className="mb-1 flex items-center gap-2 text-lg font-bold"><Droplets className="h-5 w-5 text-info" />{t("rituals.water")}</h2>
              <p className="mb-3 text-sm text-muted" data-testid="water-label">{tx(t, "rituals.glasses", { n: glasses, goal: d.water_target })}</p>
              <div className="flex flex-wrap gap-2">
                {Array.from({ length: Math.max(d.water_target, glasses) + 2 }).map((_, i) => (
                  <button key={i} aria-label={`${i + 1}`} data-testid={`glass-${i + 1}`} onClick={() => tick({ kind: "water", glasses: glasses === i + 1 ? i : i + 1 })}
                    className={cn("grid h-11 w-11 place-items-center rounded-xl border-2", i < glasses ? "border-info bg-blue-100 text-info" : "border-line bg-white text-muted")}><Droplets className="h-5 w-5" /></button>
                ))}
              </div>
            </Card>
            <Card>
              <h2 className="mb-3 flex items-center gap-2 text-lg font-bold"><Salad className="h-5 w-5 text-ok" />{t("rituals.lowSalt")}</h2>
              <button data-testid="low-salt" aria-pressed={!!e.low_salt?.done} onClick={() => tick({ kind: "low_salt", done: !e.low_salt?.done })}
                className={cn("btn w-full", e.low_salt?.done ? "bg-ok text-white" : "border border-line bg-white")}><Check className="h-4 w-4" />{e.low_salt?.done ? t("rituals.taken") : t("app.yes")}</button>
            </Card>
          </div>
          <Card>
            <h2 className="mb-3 text-lg font-bold">{t("rituals.bp")}</h2>
            <form className="flex flex-wrap items-end gap-3" onSubmit={(ev) => { ev.preventDefault(); if (sbp && dbp) { tick({ kind: "bp", sbp: Number(sbp), dbp: Number(dbp) }); setSbp(""); setDbp(""); } }}>
              <label className="w-44"><span className="label">{t("labs.sbp")}</span><input data-testid="bp-sbp" type="number" className="input" value={sbp} onChange={(x) => setSbp(x.target.value)} /></label>
              <label className="w-44"><span className="label">{t("labs.dbp")}</span><input data-testid="bp-dbp" type="number" className="input" value={dbp} onChange={(x) => setDbp(x.target.value)} /></label>
              <button className="btn-soft" data-testid="bp-save">{t("rituals.saveReading")}</button>
              {e.bp && <span className="pb-2 text-sm font-semibold">{e.bp.sbp}/{e.bp.dbp}</span>}
            </form>
          </Card>
          <Card>
            <h2 className="mb-3 text-lg font-bold">{t("rituals.symptoms")}</h2>
            <div className="flex flex-wrap gap-2">
              {SYMS.map((s) => {
                const on = symptoms.includes(s);
                const danger = ["breathless", "less_urine", "vomiting", "chest_pain"].includes(s);
                return (
                  <button key={s} data-testid={`sym-${s}`} aria-pressed={on} onClick={() => tick({ kind: "symptoms", items: on ? symptoms.filter((x) => x !== s) : [...symptoms, s] })}
                    className={cn("chip !px-3 !py-2 text-sm", on ? (danger ? "bg-rose-600 text-white" : "bg-amber-500 text-white") : "bg-slate-100 hover:bg-accent-soft")}>
                    {danger && on && <AlertTriangle className="h-3.5 w-3.5" />}{t(`rituals.symptomList.${s}`)}
                  </button>
                );
              })}
            </div>
          </Card>
        </div>
        <div className="space-y-5">
          <Card className="text-center">
            <div className="relative mx-auto grid h-36 w-24 place-items-center"><MiniKidney state={k} size={64} />
              <AnimatePresence>{sparkle > 0 && <motion.span key={sparkle} initial={{ opacity: 0, scale: 0.5, y: 0 }} animate={{ opacity: 1, scale: 1.2, y: -16 }} exit={{ opacity: 0 }} transition={{ duration: 0.8 }} className="absolute right-0 top-2 text-2xl">✨</motion.span>}</AnimatePresence></div>
            <p className="font-semibold">{t("rituals.thanks")}</p>
          </Card>
          <Card>
            <h2 className="mb-2 text-lg font-bold">{t("rituals.last14")}</h2>
            <div className="h-44"><ResponsiveContainer><BarChart data={(summary.data?.days ?? []).map((x) => ({ day: x.day, score: Math.round(x.score * 100) }))} margin={{ left: -24, right: 4 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" vertical={false} /><XAxis dataKey="day" tickFormatter={(x) => fmtDate(x, i18n.language, { day: "numeric" })} tick={{ fontSize: 10 }} /><YAxis domain={[0, 100]} tick={{ fontSize: 10 }} />
              <Tooltip labelFormatter={(x) => fmtDate(String(x), i18n.language)} /><Bar dataKey="score" fill="var(--accent)" radius={[4, 4, 0, 0]} /></BarChart></ResponsiveContainer></div>
            <p className="mt-2 text-xs text-muted">{t("rituals.private")}</p>
          </Card>
        </div>
      </div>
      <Disclaimer />
    </>
  );
}

export type { RitualKind };
