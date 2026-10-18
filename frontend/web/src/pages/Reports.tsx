import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Trash2, Upload } from "lucide-react";
import { useMemo, useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import { CartesianGrid, Line, LineChart, ReferenceArea, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { LivingKidney } from "@/components/LivingKidney";
import { Card, Chip, Disclaimer, EmptyState, ErrorState, Field, LoadingBlock, Modal, PageHeader, Segmented, Spinner, Tabs, useNotify } from "@/components/ui";
import { api, ApiError, type Lab, type LabInput, type ParsedReport, type PredictCkdInput, type PredictCkd } from "@/lib/api";
import { fmtDate, fmtNumber, stageColor, todayISO } from "@/lib/utils";
import { useSession } from "@/store/session";

const RANGES: Record<string, [number, number]> = { scr: [0.2, 30], acr: [0, 20000], sbp: [60, 260], dbp: [30, 160], hba1c: [3, 20], hgb: [3, 22], potassium: [1.5, 9], bun: [1, 250] };
const FIELDS = ["scr", "acr", "sbp", "dbp", "hba1c", "hgb", "potassium", "bun"] as const;

export default function Reports() {
  const { t } = useTranslation();
  const [tab, setTab] = useState<"labs" | "quick" | "calc">("labs");
  return (
    <>
      <PageHeader title={t("labs.title")} subtitle={t("labs.subtitle")} />
      <Tabs value={tab} onChange={setTab} tabs={[{ value: "labs", label: t("labs.history") }, { value: "quick", label: t("labs.quick.title") }, { value: "calc", label: t("labs.calc.title") }]} />
      {tab === "labs" && <LabsTab />}
      {tab === "quick" && <QuickTab />}
      {tab === "calc" && <CalcTab />}
      <Disclaimer />
    </>
  );
}

// ------------------------------------------------------------------ real sample reports (no typing needed)
const BANDS = [["normal", "Healthy", "#10b981"], ["mild", "Mild", "#65a30d"], ["moderate", "Moderate", "#f59e0b"], ["severe", "Severe", "#ea580c"], ["failure", "Failure", "#e11d48"]] as const;
function SamplesCard({ onFill, lastLab, hasLabs }: { onFill: (v: Record<string, number>) => void; lastLab?: Lab; hasLabs: boolean }) {
  const { t } = useTranslation();
  const notify = useNotify();
  const [info, setInfo] = useState("");
  const load = useMutation({
    mutationFn: (c: string) => api.reportSamples(c, 1),
    onSuccess: (r) => {
      const s = r.samples[0];
      onFill({ scr: s.scr, acr: s.acr, sbp: s.sbp, dbp: s.dbp, hba1c: s.hba1c, hgb: s.hgb, potassium: s.potassium, bun: s.bun });
      setInfo(`${r.label}: ${s.age}-year-old ${s.sex}${s.diabetes ? " with diabetes" : ""}, eGFR ${s.egfr} (${s.g_stage}). ${r.source}`);
    },
    onError: (e) => notify.error(e),
  });
  return (
    <Card data-testid="samples">
      <h2 className="mb-1 text-lg font-bold">{t("labs.sampleTitle", "Fill with a real sample report")}</h2>
      <p className="mb-3 text-sm text-muted">{t("labs.sampleBody", "Pick a kidney-function level. We fill the form from a real, de-identified adult record, so you do not have to type.")}</p>
      <div className="flex flex-wrap gap-2">
        {BANDS.map(([k, label, color]) => (
          <button key={k} type="button" className="btn-outline !min-h-[38px] !px-3 text-sm" data-testid={`sample-${k}`} disabled={load.isPending} onClick={() => load.mutate(k)}>
            <span className="h-2.5 w-2.5 rounded-full" style={{ background: color }} />{t(`labs.band_${k}`, label)}
          </button>
        ))}
      </div>
      {hasLabs && lastLab && (
        <button type="button" className="btn-ghost mt-2 !px-2 text-sm" data-testid="use-last" onClick={() => onFill(Object.fromEntries(FIELDS.filter((f) => lastLab[f] != null).map((f) => [f, lastLab[f] as number])))}>{t("labs.useLast", "Copy my last values")}</button>
      )}
      {info && <p className="mt-3 text-xs text-muted" data-testid="sample-info">{info}</p>}
    </Card>
  );
}

// ------------------------------------------------------------------ labs
function LabsTab() {
  const { t, i18n } = useTranslation();
  const qc = useQueryClient();
  const notify = useNotify();
  const user = useSession((s) => s.user)!;
  const setKidney = useSession((s) => s.setKidney);
  const labsQ = useQuery({ queryKey: ["labs"], queryFn: () => api.labs() });
  const [vals, setVals] = useState<Record<string, string>>({});
  const [date, setDate] = useState(todayISO());
  const [errs, setErrs] = useState<Record<string, string>>({});
  const [saved, setSaved] = useState<Lab | null>(null);
  const [del, setDel] = useState<Lab | null>(null);

  const add = useMutation({
    mutationFn: (b: LabInput) => api.addLab(b),
    onSuccess: async (lab) => {
      setSaved(lab); setVals({});
      notify.ok(t("labs.saved"));
      await qc.invalidateQueries({ queryKey: ["labs"] });
      try { setKidney(await api.myKidney()); qc.invalidateQueries({ queryKey: ["kidney"] }); qc.invalidateQueries({ queryKey: ["careplan"] }); } catch { /* profile incomplete */ }
    },
    onError: (e) => notify.error(e),
  });

  const submit = (e: FormEvent) => {
    e.preventDefault();
    const body: LabInput = { taken_on: date };
    const er: Record<string, string> = {};
    let any = false;
    for (const f of FIELDS) {
      const raw = vals[f];
      if (raw === undefined || raw === "") continue;
      const n = Number(raw);
      const [lo, hi] = RANGES[f];
      if (Number.isNaN(n) || n < lo || n > hi) { er[f] = t("labs.outOfRange"); continue; }
      (body as any)[f] = n; any = true;
    }
    if (!any && Object.keys(er).length === 0) er._ = t("labs.atLeastOne");
    setErrs(er);
    if (Object.keys(er).length === 0) add.mutate(body);
  };

  const remove = useMutation({
    mutationFn: (id: number) => api.deleteLab(id),
    onSuccess: async () => {
      notify.ok(t("labs.deleted")); setDel(null); setSaved(null);
      await qc.invalidateQueries({ queryKey: ["labs"] });
      try { setKidney(await api.myKidney()); qc.invalidateQueries({ queryKey: ["kidney"] }); } catch { setKidney(null); }
    },
    onError: (e) => notify.error(e),
  });

  const labs = labsQ.data ?? [];
  const chart = useMemo(() => labs.filter((l) => l.egfr !== null).map((l) => ({ date: l.taken_on, egfr: l.egfr })), [labs]);

  return (
    <div className="grid gap-6 lg:grid-cols-[420px_minmax(0,1fr)]">
      <div className="space-y-4">
        <Card>
          <h2 className="mb-3 text-lg font-bold">{t("labs.add")}</h2>
          <form onSubmit={submit} className="space-y-3" data-testid="lab-form">
            <Field label={t("labs.takenOn")} htmlFor="d"><input id="d" type="date" max={todayISO()} className="input" value={date} onChange={(e) => setDate(e.target.value)} /></Field>
            {FIELDS.map((f) => (
              <Field key={f} label={t(`labs.${f}`)} htmlFor={`f-${f}`} error={errs[f]}>
                <input id={`f-${f}`} data-testid={`lab-${f}`} inputMode="decimal" type="number" step="any" className="input" value={vals[f] ?? ""} onChange={(e) => setVals({ ...vals, [f]: e.target.value })} />
              </Field>
            ))}
            {errs._ && <p className="text-sm font-medium text-danger">{errs._}</p>}
            <button className="btn-primary w-full" disabled={add.isPending} data-testid="lab-save">{add.isPending ? <Spinner className="text-white" /> : t("app.save")}</button>
          </form>
        </Card>
        <SamplesCard hasLabs={labs.length > 0} onFill={(v) => { setVals(Object.fromEntries(Object.entries(v).map(([k, x]) => [k, String(x)]))); setErrs({}); setDate(todayISO()); }} lastLab={labs[labs.length - 1]} />
        <UploadCard onApply={(vals, taken) => { setVals(Object.fromEntries(Object.entries(vals).map(([k, v]) => [k, String(v)]))); if (taken) setDate(taken); setErrs({}); }} />
      </div>

      <div className="space-y-4">
        {saved && <AnalysisCard lab={saved} hasProfile={user.birth_year !== null && user.sex !== null} />}
        <Card>
          <h2 className="mb-3 text-lg font-bold">{t("labs.history")}</h2>
          {labsQ.isLoading ? <LoadingBlock /> : labsQ.error ? <ErrorState error={labsQ.error} onRetry={() => labsQ.refetch()} /> : labs.length === 0 ? (
            <EmptyState title={t("app.noData")} body={t("labs.subtitle")} />
          ) : (
            <>
              {chart.length > 0 && (
                <div className="mb-4 h-64 w-full" data-testid="egfr-chart">
                  <ResponsiveContainer>
                    <LineChart data={chart} margin={{ top: 8, right: 12, bottom: 0, left: -12 }}>
                      <ReferenceArea y1={90} y2={140} fill="#10b981" fillOpacity={0.08} /><ReferenceArea y1={60} y2={90} fill="#65a30d" fillOpacity={0.08} />
                      <ReferenceArea y1={30} y2={60} fill="#f59e0b" fillOpacity={0.1} /><ReferenceArea y1={15} y2={30} fill="#ea580c" fillOpacity={0.1} /><ReferenceArea y1={0} y2={15} fill="#e11d48" fillOpacity={0.12} />
                      <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                      <XAxis dataKey="date" tickFormatter={(d) => fmtDate(d, i18n.language, { month: "short", year: "2-digit" })} tick={{ fontSize: 12 }} />
                      <YAxis domain={[0, 120]} tick={{ fontSize: 12 }} />
                      <Tooltip labelFormatter={(d) => fmtDate(String(d), i18n.language)} />
                      <Line type="monotone" dataKey="egfr" name="eGFR" stroke="var(--accent)" strokeWidth={3} dot={{ r: 4 }} />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              )}
              <div className="overflow-x-auto">
                <table className="w-full min-w-[620px] text-left text-sm">
                  <thead className="text-xs uppercase text-muted"><tr>{["labs.takenOn", "labs.scr", "labs.egfr", "labs.stage", "labs.acr", "labs.sbp", "labs.hba1c", "labs.hgb", "labs.potassium", ""].map((h, i) => <th key={i} className="px-2 py-2">{h ? t(h).split("(")[0] : ""}</th>)}</tr></thead>
                  <tbody>
                    {[...labs].reverse().map((l) => (
                      <tr key={l.id} className="border-t border-line" data-testid="lab-row">
                        <td className="px-2 py-2">{fmtDate(l.taken_on, i18n.language)}</td><td className="px-2">{fmtNumber(l.scr, i18n.language)}</td>
                        <td className="px-2 font-semibold">{fmtNumber(l.egfr, i18n.language)}</td>
                        <td className="px-2">{l.g_stage ? <span className="chip text-white" style={{ background: stageColor(l.g_stage) }}>{l.g_stage}</span> : "-"}</td>
                        <td className="px-2">{fmtNumber(l.acr, i18n.language)}</td><td className="px-2">{fmtNumber(l.sbp, i18n.language)}</td>
                        <td className="px-2">{fmtNumber(l.hba1c, i18n.language)}</td><td className="px-2">{fmtNumber(l.hgb, i18n.language)}</td><td className="px-2">{fmtNumber(l.potassium, i18n.language)}</td>
                        <td className="px-2"><button className="btn-ghost !min-h-[36px] !px-2 text-danger" aria-label={t("app.delete")} onClick={() => setDel(l)}><Trash2 className="h-4 w-4" /></button></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          )}
        </Card>
      </div>
      <Modal open={!!del} onClose={() => setDel(null)} title={t("app.delete")}>
        <p className="mb-4">{del && fmtDate(del.taken_on, i18n.language)}</p>
        <div className="flex justify-end gap-2"><button className="btn-outline" onClick={() => setDel(null)}>{t("app.cancel")}</button>
          <button className="btn-danger" disabled={remove.isPending} onClick={() => del && remove.mutate(del.id)} data-testid="confirm-delete">{t("app.delete")}</button></div>
      </Modal>
    </div>
  );
}


// ------------------------------------------------------------------ upload / paste a lab report
function UploadCard({ onApply }: { onApply: (vals: Record<string, number>, taken: string | null) => void }) {
  const { t } = useTranslation();
  const notify = useNotify();
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [res, setRes] = useState<ParsedReport | null>(null);
  const [msg, setMsg] = useState("");

  const run = async (fn: () => Promise<ParsedReport>) => {
    setBusy(true); setMsg(""); setRes(null);
    try { setRes(await fn()); }
    catch (e) {
      const d = e instanceof ApiError ? e.detail : null;
      if (e instanceof ApiError && e.status === 415) setMsg(d?.code === "unsupported" ? t("upload.unsupported") : t("upload.ocrNeeded"));
      else if (e instanceof ApiError && e.status === 413) setMsg(t("upload.tooBig"));
      else notify.error(e);
    } finally { setBusy(false); }
  };
  const label = (k: string) => (k === "scr" ? t("labs.scr") : k === "bun" ? t("labs.bun") : t(`labs.${k}`));

  return (
    <Card data-testid="upload-card">
      <div className="mb-3 flex items-center gap-3"><Upload className="h-6 w-6 text-accent" /><p className="font-semibold">{t("labs.uploadTitle")}</p></div>
      <label className="btn-outline w-full cursor-pointer"><input data-testid="upload-file" type="file" className="sr-only" accept=".pdf,.txt,.csv,image/*" onChange={(e) => { const f = e.target.files?.[0]; if (f) void run(() => api.reportsParseFile(f)); e.target.value = ""; }} />{t("upload.choose")}</label>
      <Field label={t("upload.paste")}><textarea data-testid="upload-text" className="input min-h-[90px]" value={text} onChange={(e) => setText(e.target.value)} maxLength={20000} /></Field>
      <button className="btn-soft mt-2 w-full" disabled={busy || !text.trim()} onClick={() => run(() => api.reportsParseText(text))} data-testid="upload-read">{busy ? <Spinner /> : t("upload.read")}</button>
      {msg && <p className="mt-3 rounded-xl bg-amber-50 p-3 text-sm text-amber-900" data-testid="upload-msg">{msg}</p>}
      {res && (
        <div className="mt-3 space-y-2" data-testid="upload-result">
          {res.matched.length === 0 ? <p className="rounded-xl bg-amber-50 p-3 text-sm text-amber-900">{t("upload.nothing")}</p> : (<>
            <p className="text-sm font-semibold">{t("upload.found")}</p>
            <ul className="divide-y divide-line rounded-xl border border-line text-sm">{res.matched.map((m) => <li key={m.field} className="flex items-center justify-between gap-2 px-3 py-2"><span>{label(m.field).split("(")[0]}</span><b>{m.value}</b><span className="text-xs text-muted">{m.unit}</span></li>)}</ul>
            {res.taken_on && <p className="text-xs text-muted">{t("labs.takenOn")}: {res.taken_on}</p>}
            <button className="btn-primary w-full" onClick={() => onApply(res.values as Record<string, number>, res.taken_on)} data-testid="upload-apply">{t("upload.apply")}</button>
          </>)}
        </div>
      )}
    </Card>
  );
}

function AnalysisCard({ lab, hasProfile }: { lab: Lab; hasProfile: boolean }) {
  const { t } = useTranslation();
  const stage = useQuery({ queryKey: ["stage", lab.egfr, lab.acr], queryFn: () => api.stage({ egfr: lab.egfr!, acr: lab.acr ?? undefined }), enabled: lab.egfr !== null });
  const kidney = useQuery({ queryKey: ["kidney", "me"], queryFn: () => api.myKidney(), enabled: hasProfile });
  return (
    <Card className="border-accent/40" data-testid="analysis">
      <h2 className="mb-3 text-lg font-bold">{t("labs.analysis")}</h2>
      {lab.egfr === null ? <p className="rounded-xl bg-amber-50 p-3 text-amber-900">{t("labs.profileWarning")} <Link to="/onboarding" className="font-semibold underline">{t("onboarding.title")}</Link></p> : (
        <div className="grid items-center gap-4 sm:grid-cols-[180px_minmax(0,1fr)]">
          {kidney.data?.has_data ? <LivingKidney state={kidney.data} size="md" showEcg={false} /> : <div className="skeleton h-48" />}
          <div className="space-y-2">
            <p className="text-3xl font-extrabold">eGFR {fmtNumber(lab.egfr, "en")}</p>
            <div className="flex flex-wrap gap-2">
              {lab.g_stage && <span className="chip text-white" style={{ background: stageColor(lab.g_stage) }}>{t(`gStage.${lab.g_stage}`)}</span>}
              {stage.data?.a_category && <Chip>{stage.data.a_category}</Chip>}
              {stage.data?.ckd_by_labs && <Chip tone="warn">CKD?</Chip>}
            </div>
            {kidney.data?.has_data && <p>{t(`stageDesc.${kidney.data.stage_name}`)}</p>}
            {stage.data && <p className="text-xs text-muted">{stage.data.note}</p>}
            {kidney.data?.has_data && kidney.data.wounds.filter((w) => w.level > 0.1).slice(0, 3).map((w) => <p key={w.code} className="text-sm">• {t(`wounds.${w.code}.cause`)}</p>)}
            <div className="flex flex-wrap gap-2 pt-1">
              <Link to="/care" className="btn-primary">{t("labs.goCareLab")}</Link>
              <Link to="/forecast" className="btn-outline">{t("labs.seeTimeMachine")}</Link>
            </div>
          </div>
        </div>
      )}
    </Card>
  );
}

// ------------------------------------------------------------------ quick CKD check
function QuickTab() {
  const { t } = useTranslation();
  const user = useSession((s) => s.user)!;
  const notify = useNotify();
  const [f, setF] = useState<Record<string, string>>({ age: user.age ? String(user.age) : "" });
  const [flags, setFlags] = useState<Record<string, boolean>>({ htn: user.hypertension, dm: user.diabetes });
  const [al, setAl] = useState<number | null>(null);
  const [su, setSu] = useState<number | null>(null);
  const [res, setRes] = useState<PredictCkd | null>(null);
  const m = useMutation({ mutationFn: (b: PredictCkdInput) => api.predictCkd(b), onSuccess: setRes, onError: (e) => notify.error(e) });

  const run = (e: FormEvent) => {
    e.preventDefault();
    const b: any = { age: Number(f.age) };
    for (const k of ["bp", "bgr", "bu", "sc", "hemo"]) if (f[k]) b[k] = Number(f[k]);
    if (al !== null) b.al = al; if (su !== null) b.su = su;
    for (const [k, v] of Object.entries(flags)) if (v) b[k === "appet" ? "appet_poor" : k] = true;
    m.mutate(b);
  };
  const num = (k: string, label: string) => (
    <Field label={label} htmlFor={`q-${k}`}><input id={`q-${k}`} data-testid={`q-${k}`} type="number" step="any" className="input" value={f[k] ?? ""} onChange={(e) => setF({ ...f, [k]: e.target.value })} /></Field>
  );
  const strip = (label: string, v: number | null, set: (n: number | null) => void) => (
    <Field label={label}><div className="flex gap-1.5">{[0, 1, 2, 3, 4, 5].map((n) => <button type="button" key={n} onClick={() => set(v === n ? null : n)} className={`h-11 w-11 rounded-xl border-2 font-semibold ${v === n ? "border-accent bg-accent text-white" : "border-line bg-white"}`}>{n}</button>)}</div></Field>
  );
  const tone = res?.risk_level === "high" ? "danger" : res?.risk_level === "moderate" ? "warn" : "ok";
  return (
    <div className="grid gap-6 lg:grid-cols-2">
      <Card>
        <p className="mb-3 text-muted">{t("labs.quick.intro")}</p>
        <form onSubmit={run} className="grid gap-3 sm:grid-cols-2">
          <div className="sm:col-span-2">{num("age", t("onboarding.birthYear").replace(/.*/, "Age"))}</div>
          {num("bp", t("labs.quick.bp"))}{num("sc", t("labs.scr"))}{num("bu", t("labs.bun"))}{num("hemo", t("labs.hgb"))}{num("bgr", t("labs.quick.bgr"))}
          <div className="sm:col-span-2 grid gap-3 sm:grid-cols-2">{strip(t("labs.quick.al"), al, setAl)}{strip(t("labs.quick.su"), su, setSu)}</div>
          <div className="sm:col-span-2 grid grid-cols-2 gap-1">
            {([["htn", t("onboarding.hypertension")], ["dm", t("onboarding.diabetes")], ["cad", t("labs.quick.cad")], ["appet", t("labs.quick.appet")], ["pe", t("labs.quick.pe")], ["ane", t("labs.quick.ane")]] as const).map(([k, label]) => (
              <label key={k} className="flex min-h-[44px] items-center gap-2"><input type="checkbox" className="h-5 w-5 accent-[var(--accent)]" checked={!!flags[k]} onChange={(e) => setFlags({ ...flags, [k]: e.target.checked })} />{label}</label>
            ))}
          </div>
          <button className="btn-primary sm:col-span-2" disabled={m.isPending || !f.age} data-testid="q-run">{m.isPending ? <Spinner className="text-white" /> : t("labs.calc.run")}</button>
        </form>
      </Card>
      <Card data-testid="q-result">
        {!res ? <EmptyState title={t("labs.quick.title")} body={t("labs.quick.intro")} /> : (
          <div className="space-y-4">
            <div className="flex items-center gap-5">
              <div className="grid h-28 w-28 place-items-center rounded-full border-[10px] text-2xl font-extrabold" style={{ borderColor: tone === "danger" ? "#e11d48" : tone === "warn" ? "#f59e0b" : "#10b981" }}>{Math.round(res.probability_ckd * 100)}%</div>
              <div><p className="text-sm text-muted">{t("labs.quick.result")}</p><Chip tone={tone as any}>{t(`labs.quick.${res.risk_level}`)}</Chip>
                <p className="mt-2 text-sm text-muted" data-testid="q-answered">{res.inputs_given}/{res.inputs_total}</p></div>
            </div>
            {res.top_drivers.length > 0 && (
              <div><p className="mb-2 font-semibold">{t("labs.quick.drivers")}</p>
                <ul className="space-y-2">{res.top_drivers.map((d) => (
                  <li key={d.feature} className="text-sm"><div className="flex justify-between"><span className="font-medium">{driverLabel(d.feature, t)}</span><span className="text-muted">{d.pushes.includes("towards") ? t("labs.quick.pushesToward") : t("labs.quick.pushesAway")}</span></div>
                    <div className="mt-1 h-2 rounded-full bg-slate-100"><div className={`h-2 rounded-full ${d.pushes.includes("towards") ? "bg-danger" : "bg-ok"}`} style={{ width: `${Math.min(100, d.strength * 40)}%` }} /></div></li>
                ))}</ul>
              </div>
            )}
            <p className="text-xs text-muted">{res.note}</p>
          </div>
        )}
      </Card>
    </div>
  );
}

function driverLabel(f: string, t: (k: string) => string) {
  const map: Record<string, string> = { sc: "labs.scr", bu: "labs.bun", hemo: "labs.hgb", bgr: "labs.quick.bgr", bp: "labs.quick.bp", al: "labs.quick.al", su: "labs.quick.su", htn: "onboarding.hypertension", dm: "onboarding.diabetes", cad: "labs.quick.cad", appet: "labs.quick.appet", pe: "labs.quick.pe", ane: "labs.quick.ane" };
  return map[f] ? t(map[f]).split("(")[0] : f;
}

// ------------------------------------------------------------------ eGFR calculator
function CalcTab() {
  const { t } = useTranslation();
  const user = useSession((s) => s.user)!;
  const notify = useNotify();
  const [scr, setScr] = useState("");
  const [age, setAge] = useState(user.age ? String(user.age) : "");
  const [sex, setSex] = useState<"male" | "female">(user.sex ?? "male");
  const [acr, setAcr] = useState("");
  const [out, setOut] = useState<{ egfr: number; g_stage: string; a?: string | null } | null>(null);
  const run = async (e: FormEvent) => {
    e.preventDefault();
    try {
      const r = await api.egfr({ scr: Number(scr), age: Number(age), sex });
      let a: string | null = null;
      if (acr) a = (await api.stage({ egfr: r.egfr, acr: Number(acr) })).a_category;
      setOut({ ...r, a });
    } catch (er) { notify.error(er); }
  };
  return (
    <Card className="max-w-xl">
      <form onSubmit={run} className="space-y-3">
        <Field label={t("labs.scr")}><input data-testid="c-scr" required type="number" step="any" className="input" value={scr} onChange={(e) => setScr(e.target.value)} /></Field>
        <Field label="Age"><input data-testid="c-age" required type="number" className="input" value={age} onChange={(e) => setAge(e.target.value)} /></Field>
        <Field label={t("onboarding.sex")}><Segmented value={sex} onChange={setSex} options={[{ value: "male", label: t("onboarding.male") }, { value: "female", label: t("onboarding.female") }]} /></Field>
        <Field label={t("labs.acr")}><input type="number" step="any" className="input" value={acr} onChange={(e) => setAcr(e.target.value)} /></Field>
        <button className="btn-primary w-full" data-testid="c-run">{t("labs.calc.run")}</button>
      </form>
      {out && <div className="mt-4 rounded-xl2 bg-accent-soft p-4" data-testid="c-result"><p className="text-xl font-bold">{t("labs.calc.result", { egfr: fmtNumber(out.egfr, "en"), stage: t(`gStage.${out.g_stage}`) })}</p>{out.a && <p className="mt-1">ACR: {out.a}</p>}</div>}
    </Card>
  );
}
