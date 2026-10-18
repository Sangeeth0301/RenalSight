import { useMutation, useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import { Area, CartesianGrid, ComposedChart, Line, ReferenceArea, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { LivingKidney, NO_STATE } from "@/components/LivingKidney";
import { Card, Chip, Disclaimer, EmptyState, ErrorState, EstimateChip, LoadingBlock, PageHeader, Segmented, Spinner, useDebounced, useNotify } from "@/components/ui";
import { api, ApiError, type Forecast as FC } from "@/lib/api";
import { fmtNumber, latest, tx } from "@/lib/utils";
import { useSession } from "@/store/session";

type Scenario = "no_change" | "good_care";
const pct = (v: number) => `${Math.round(v * 100)}%`;

export default function Forecast() {
  const { t, i18n } = useTranslation();
  const user = useSession((s) => s.user)!;
  const notify = useNotify();
  const [scenario, setScenario] = useState<Scenario>("no_change");
  const [compare, setCompare] = useState(false);
  const [year, setYear] = useState(0);
  const [wi, setWi] = useState<{ sbp?: number; hba1c?: number; acr?: number }>({});

  const labsQ = useQuery({ queryKey: ["labs"], queryFn: () => api.labs() });
  const fq = useQuery({ queryKey: ["forecast", scenario], queryFn: () => api.myForecast(scenario, 15), retry: false });
  const fq2 = useQuery({ queryKey: ["forecast", scenario === "no_change" ? "good_care" : "no_change"], queryFn: () => api.myForecast(scenario === "no_change" ? "good_care" : "no_change", 15), enabled: compare, retry: false });

  const labs = labsQ.data ?? [];
  const withEgfr = labs.filter((l) => l.egfr !== null);
  const cur = {
    egfr: withEgfr.length ? withEgfr[withEgfr.length - 1].egfr! : undefined,
    sbp: latest(labs, "sbp"), hba1c: latest(labs, "hba1c"), acr: latest(labs, "acr"), hgb: latest(labs, "hgb"), potassium: latest(labs, "potassium"),
  };
  const base = useMemo(() => {
    if (!user.age || !user.sex || cur.egfr === undefined) return null;
    const first = withEgfr[0]?.taken_on;
    const history = withEgfr.length >= 3 && first ? withEgfr.map((l) => ({ month: (new Date(l.taken_on).getTime() - new Date(first).getTime()) / (30.44 * 86400000), egfr: l.egfr! })) : [];
    return { age: user.age, sex: user.sex, egfr: cur.egfr, diabetes: user.diabetes, sbp: cur.sbp ?? null, hba1c: cur.hba1c ?? null, acr: cur.acr ?? null, history };
  }, [user, cur.egfr, cur.sbp, cur.hba1c, cur.acr, withEgfr]);

  const f = fq.data;
  const idx = f?.years ? Math.min(f.years.findIndex((y) => y >= year), f.years.length - 1) : 0;
  const ageEgfr = f && f.has_data !== false ? f.egfr_p50[Math.max(idx, 0)] : undefined;
  const dKidney = useDebounced({ egfr: ageEgfr, acr: cur.acr, sbp: cur.sbp, hgb: cur.hgb, potassium: cur.potassium }, 250);
  const kq = useQuery({
    queryKey: ["kidney-at-year", dKidney, user.sex],
    queryFn: () => api.kidneyState({ egfr: dKidney.egfr!, acr: dKidney.acr, sbp: dKidney.sbp, hgb: dKidney.hgb, potassium: dKidney.potassium, sex: user.sex ?? undefined }),
    enabled: dKidney.egfr !== undefined, placeholderData: (p) => p,
  });

  const kfre = useQuery({ queryKey: ["kfre", base?.egfr, base?.acr, base?.age], queryFn: () => api.kfre({ age: base!.age, sex: base!.sex, egfr: base!.egfr, acr: base!.acr! }), enabled: !!base && base.acr !== null && base.egfr >= 15 && base.egfr < 60, retry: false });
  const surv = useQuery({
    queryKey: ["survival", base?.egfr, base?.acr, base?.age, base?.sbp, base?.hba1c, cur.hgb], retry: false, enabled: !!base,
    queryFn: () => api.survival({ age: Math.max(base!.age, 20), sex: base!.sex, egfr: base!.egfr, acr: base!.acr ?? undefined, diabetes: base!.diabetes, sbp: base!.sbp ?? undefined, hba1c: base!.hba1c ?? undefined, hgb: cur.hgb }),
  });

  const whatIf = useMutation({
    mutationFn: () => api.whatIf({ base: { ...base!, scenario: "no_change", horizon_years: 15 }, sbp: wi.sbp, hba1c: base!.diabetes ? wi.hba1c : undefined, acr: wi.acr }),
    onError: (e) => notify.error(e),
  });

  const data = useMemo(() => (f?.years ?? []).map((y, i) => ({ year: y, median: f!.egfr_p50[i], band: [f!.egfr_p10[i], f!.egfr_p90[i]], other: fq2.data?.egfr_p50?.[i] })), [f, fq2.data]);

  if (labsQ.isLoading || fq.isLoading) return <LoadingBlock rows={4} />;
  const noLabs = (fq.error instanceof ApiError && fq.error.status === 422) || (f && f.has_data === false) || withEgfr.length === 0;
  if (noLabs) return (<><PageHeader title={t("forecast.title")} subtitle={t("forecast.subtitle")} /><EmptyState title={t("forecast.needLabs")} action={<Link to="/reports" className="btn-primary">{t("labs.add")}</Link>} /></>);
  if (fq.error) return <ErrorState error={fq.error} onRetry={() => fq.refetch()} />;
  const fc = f as FC;
  const horizon = 15;
  const cases: [string, number | null][] = [["fast", fc.years_to_stage5_p10], ["expected", fc.years_to_stage5_p50], ["slow", fc.years_to_stage5_p90]];

  const sliders = base ? { sbp: wi.sbp ?? base.sbp ?? 130, hba1c: wi.hba1c ?? base.hba1c ?? 7, acr: wi.acr ?? base.acr ?? 30 } : null;

  return (
    <>
      <PageHeader title={t("forecast.title")} subtitle={t("forecast.subtitle")} chip={<EstimateChip />}
        right={<div className="flex flex-wrap items-center gap-3"><Segmented value={scenario} onChange={setScenario} options={[{ value: "no_change", label: t("forecast.noChange") }, { value: "good_care", label: t("forecast.goodCare") }]} />
          <label className="flex min-h-[44px] items-center gap-2 text-sm font-medium"><input type="checkbox" className="h-5 w-5 accent-[var(--accent)]" checked={compare} onChange={(e) => setCompare(e.target.checked)} />vs {scenario === "no_change" ? t("forecast.goodCare") : t("forecast.noChange")}</label></div>} />

      <div className="grid gap-6 lg:grid-cols-[340px_minmax(0,1fr)]">
        <Card className="flex flex-col items-center">
          <LivingKidney state={kq.data ?? NO_STATE} size="lg" showEcg={false} />
          <p className="mt-3 text-lg font-bold">{t(`stages.${(kq.data ?? NO_STATE).stage_name}`)}</p>
          <p className="text-sm text-muted">{t("forecast.slider")}: <b data-testid="year-label">{year}</b></p>
          <input data-testid="year-slider" type="range" min={0} max={horizon} step={0.5} value={year} onChange={(e) => setYear(Number(e.target.value))} className="mt-2 w-full accent-[var(--accent)]" aria-label={t("forecast.slider")} />
          {ageEgfr !== undefined && <p className="mt-1 text-sm">eGFR ≈ <b>{fmtNumber(ageEgfr, i18n.language)}</b> ({fmtNumber(fc.egfr_p10[Math.max(idx, 0)], i18n.language)}–{fmtNumber(fc.egfr_p90[Math.max(idx, 0)], i18n.language)})</p>}
        </Card>

        <div className="space-y-6">
          <Card>
            <div className="mb-2 flex flex-wrap items-center justify-between gap-2"><h2 className="text-lg font-bold">{t("forecast.chart")}</h2>
              <Chip tone="slate">{fc.uses_own_trend ? t("forecast.ownTrend") : t("forecast.typicalTrend")}</Chip></div>
            <div className="h-72 w-full" data-testid="forecast-chart">
              <ResponsiveContainer>
                <ComposedChart data={data} margin={{ top: 8, right: 12, bottom: 0, left: -12 }}>
                  <ReferenceArea y1={0} y2={15} fill="#e11d48" fillOpacity={0.12} />
                  <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                  <XAxis dataKey="year" type="number" domain={[0, horizon]} tick={{ fontSize: 12 }} />
                  <YAxis domain={[0, 120]} tick={{ fontSize: 12 }} />
                  <Tooltip formatter={(v: any) => (Array.isArray(v) ? `${fmtNumber(v[0], i18n.language)}–${fmtNumber(v[1], i18n.language)}` : fmtNumber(v, i18n.language))} labelFormatter={(y) => `${y}`} />
                  <ReferenceLine y={60} stroke="#94a3b8" strokeDasharray="4 4" label={{ value: "G3", fontSize: 11, position: "right" }} />
                  <ReferenceLine y={30} stroke="#94a3b8" strokeDasharray="4 4" label={{ value: "G4", fontSize: 11, position: "right" }} />
                  <ReferenceLine y={15} stroke="#e11d48" strokeDasharray="4 4" label={{ value: "G5", fontSize: 11, position: "right" }} />
                  <ReferenceLine x={year} stroke="var(--accent)" strokeWidth={2} />
                  <Area dataKey="band" name={t("forecast.range")} stroke="none" fill="var(--accent)" fillOpacity={0.18} />
                  <Line dataKey="median" name={t("forecast.expected")} stroke="var(--accent)" strokeWidth={3} dot={false} />
                  {compare && <Line dataKey="other" name={scenario === "no_change" ? t("forecast.goodCare") : t("forecast.noChange")} stroke="#64748b" strokeDasharray="6 4" strokeWidth={2} dot={false} />}
                </ComposedChart>
              </ResponsiveContainer>
            </div>
          </Card>

          {fc.already_stage5 ? <Card className="border-rose-300 bg-rose-50"><p className="font-semibold text-rose-900">{t("forecast.alreadyStage5")}</p></Card> : (
            <Card>
              <h2 className="mb-3 text-lg font-bold">{t("forecast.yearsToStage5")}</h2>
              <div className="grid gap-3 sm:grid-cols-3">
                {cases.map(([k, v]) => (
                  <div key={k} className={`rounded-xl2 border p-4 text-center ${k === "expected" ? "border-accent bg-accent-soft" : "border-line"}`} data-testid={`case-${k}`}>
                    <p className="text-sm text-muted">{t(`forecast.${k}`)}</p>
                    <p className="text-2xl font-extrabold">{v === null ? t("forecast.beyond", { years: 30 }) : fmtNumber(v, i18n.language)}</p>
                  </div>
                ))}
              </div>
              <div className="mt-4 grid grid-cols-3 gap-3">
                {([[2, fc.prob_kf_2y], [5, fc.prob_kf_5y], [10, fc.prob_kf_10y]] as const).map(([y, p]) => (
                  <div key={y} className="text-center"><div className="mx-auto grid h-20 w-20 place-items-center rounded-full border-[8px] text-lg font-bold" style={{ borderColor: p > 0.5 ? "#e11d48" : p > 0.2 ? "#f59e0b" : "#10b981" }}>{pct(p)}</div>
                    <p className="mt-1 text-xs text-muted">{t("forecast.chance", { years: y })}</p></div>
                ))}
              </div>
            </Card>
          )}

          {sliders && base && (
            <Card>
              <h2 className="mb-3 text-lg font-bold">{t("forecast.whatIf")}</h2>
              <div className="grid gap-4 sm:grid-cols-3">
                <Slider label={t("forecast.sbp")} min={90} max={200} step={1} value={sliders.sbp} onChange={(v) => setWi({ ...wi, sbp: v })} testid="wi-sbp" />
                {base.diabetes && <Slider label={t("forecast.hba1c")} min={4} max={14} step={0.1} value={sliders.hba1c} onChange={(v) => setWi({ ...wi, hba1c: v })} testid="wi-hba1c" />}
                <Slider label={t("forecast.acr")} min={5} max={3000} step={5} value={sliders.acr} onChange={(v) => setWi({ ...wi, acr: v })} testid="wi-acr" />
              </div>
              <button className="btn-primary mt-4" onClick={() => whatIf.mutate()} disabled={whatIf.isPending} data-testid="wi-apply">{whatIf.isPending ? <Spinner className="text-white" /> : t("forecast.apply")}</button>
              {whatIf.data && (
                <div className="mt-4 grid gap-3 sm:grid-cols-3" data-testid="wi-result">
                  <div className="rounded-xl2 border border-line p-3 text-center"><p className="text-sm text-muted">{t("forecast.noChange")}</p><p className="text-xl font-bold">{whatIf.data.baseline.years_to_stage5_p50 === null ? t("forecast.beyond", { years: 30 }) : fmtNumber(whatIf.data.baseline.years_to_stage5_p50, i18n.language)}</p></div>
                  <div className="rounded-xl2 border border-accent bg-accent-soft p-3 text-center"><p className="text-sm text-muted">{t("forecast.whatIf")}</p><p className="text-xl font-bold">{whatIf.data.modified.years_to_stage5_p50 === null ? t("forecast.beyond", { years: 30 }) : fmtNumber(whatIf.data.modified.years_to_stage5_p50, i18n.language)}</p></div>
                  <div className="rounded-xl2 bg-emerald-50 p-3 text-center font-semibold text-emerald-800">{whatIf.data.difference_years_median !== null && whatIf.data.difference_years_median > 0 ? tx(t, "forecast.gain", { years: fmtNumber(whatIf.data.difference_years_median, i18n.language) }) : "-"}</div>
                </div>
              )}
            </Card>
          )}

          <div className="grid gap-6 md:grid-cols-2">
            {kfre.data && (
              <Card><h2 className="mb-3 text-lg font-bold">{t("forecast.kfreTitle")}</h2>
                <div className="grid grid-cols-2 gap-3 text-center"><div><p className="text-3xl font-extrabold">{pct(kfre.data.risk_2y)}</p><p className="text-xs text-muted">{t("forecast.kfre2")}</p></div><div><p className="text-3xl font-extrabold">{pct(kfre.data.risk_5y)}</p><p className="text-xs text-muted">{t("forecast.kfre5")}</p></div></div></Card>
            )}
            {surv.data && (
              <Card data-testid="outlook"><h2 className="text-lg font-bold">{t("forecast.outlookTitle")}</h2><p className="mb-3 text-sm text-muted">{t("forecast.outlookBody")}</p>
                {([["year1", surv.data.survival_1y], ["year3", surv.data.survival_3y], ["year5", surv.data.survival_5y]] as const).map(([k, v]) => (
                  <div key={k} className="mb-2"><div className="flex justify-between text-sm"><span>{t(`forecast.${k}`)}</span><b>{pct(v)}</b></div><div className="h-2.5 rounded-full bg-slate-100"><div className="h-2.5 rounded-full bg-accent" style={{ width: pct(v) }} /></div></div>
                ))}
                <p className="mt-2 text-xs text-muted">{t("forecast.outlookNote")}</p></Card>
            )}
          </div>

          {fc.assumptions?.length > 0 && (
            <Card><p className="mb-1 text-sm font-semibold">{t("forecast.assumed", { list: "" }).replace(/:\s*$/, "")}</p><ul className="list-disc pl-5 text-sm text-muted">{fc.assumptions.map((a) => <li key={a}>{a}</li>)}</ul></Card>
          )}
          <p className="text-center text-sm text-muted">{t("forecast.simNote")}</p>
        </div>
      </div>
      <Disclaimer />
    </>
  );
}

function Slider({ label, min, max, step, value, onChange, testid }: { label: string; min: number; max: number; step: number; value: number; onChange: (v: number) => void; testid: string }) {
  return (
    <label className="block"><span className="label">{label}: <b>{value}</b></span>
      <input data-testid={testid} type="range" min={min} max={max} step={step} value={value} onChange={(e) => onChange(Number(e.target.value))} className="w-full accent-[var(--accent)]" /></label>
  );
}
