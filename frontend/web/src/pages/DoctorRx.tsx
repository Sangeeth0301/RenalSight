import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, ArrowLeft, Download, FilePlus2, Info, Plus, Printer, ShieldCheck, Trash2 } from "lucide-react";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, useNavigate, useParams } from "react-router-dom";
import { LivingKidney } from "@/components/LivingKidney";
import { Card, Chip, ErrorState, Field, LoadingBlock, Modal, PageHeader, Spinner, useNotify } from "@/components/ui";
import { api, ApiError, type Rx, type RxItem, type Safety } from "@/lib/api";
import { currentLang } from "@/i18n";
import { fmtDate, fmtNumber, tx } from "@/lib/utils";

type Row = Partial<RxItem> & { drug_key: string; drug_name: string };

export default function DoctorRx() {
  const { t, i18n } = useTranslation();
  const { id } = useParams();
  const rid = Number(id);
  const nav = useNavigate();
  const qc = useQueryClient();
  const notify = useNotify();
  const rxQ = useQuery({ queryKey: ["rx", rid], queryFn: () => api.rx(rid) });
  const formQ = useQuery({ queryKey: ["rx", "formulary"], queryFn: () => api.rxFormulary() });
  const [rows, setRows] = useState<Row[]>([]);
  const [safety, setSafety] = useState<Safety | null>(null);
  const [dirty, setDirty] = useState(false);
  const [notes, setNotes] = useState("");
  const [override, setOverride] = useState<{ safety: Safety } | null>(null);
  const [reason, setReason] = useState("");
  const [rejectOpen, setRejectOpen] = useState(false);
  const [rejectReason, setRejectReason] = useState("");
  const [custom, setCustom] = useState("");

  const rx = rxQ.data;
  useEffect(() => {
    if (!rx) return;
    setRows(rx.items.filter((i): i is RxItem => "drug_name" in i).map((i) => ({ ...i })));
    setSafety(rx.safety ?? null);
    setNotes(rx.doctor_notes ?? "");
    setDirty(false);
  }, [rx?.id, rx?.status, rx?.items.length]); // eslint-disable-line react-hooks/exhaustive-deps

  const editable = rx?.status === "draft" || rx?.status === "submitted";
  const apply = (r: Rx) => { qc.setQueryData(["rx", rid], r); void qc.invalidateQueries({ queryKey: ["doctor"] }); void qc.invalidateQueries({ queryKey: ["rx", "list"] }); };

  const save = useMutation({
    mutationFn: () => api.rxSetItems(rid, rows.map(({ id: _id, ...rest }) => rest)),
    onSuccess: (r) => { apply(r); setSafety(r.safety ?? null); setDirty(false); },
    onError: (e) => notify.error(e),
  });
  const check = useMutation({ mutationFn: () => api.rxSafety(rid), onSuccess: (s) => setSafety(s), onError: (e) => notify.error(e) });
  const sign = useMutation({
    mutationFn: (override_reason?: string) => api.rxSign(rid, { notes: notes || undefined, override_reason }),
    onSuccess: (r) => { apply(r); setOverride(null); setReason(""); notify.ok(t("rx.status.signed")); },
    onError: (e) => {
      if (e instanceof ApiError && e.status === 409 && typeof e.detail === "object" && e.detail?.safety) { setSafety(e.detail.safety); setOverride({ safety: e.detail.safety }); }
      else notify.error(e);
    },
  });
  const reject = useMutation({ mutationFn: () => api.rxReject(rid, rejectReason), onSuccess: (r) => { apply(r); setRejectOpen(false); }, onError: (e) => notify.error(e) });
  const revise = useMutation({ mutationFn: () => api.rxRevise(rid), onSuccess: (r) => { void qc.invalidateQueries({ queryKey: ["rx"] }); nav(`/doctor/rx/${r.id}`); }, onError: (e) => notify.error(e) });

  const update = (i: number, patch: Partial<Row>) => { setRows((p) => p.map((r, n) => (n === i ? { ...r, ...patch } : r))); setDirty(true); };
  const addDrug = (key: string) => {
    const f = formQ.data?.[key];
    if (f) setRows((p) => [...p, { drug_key: key, drug_name: f.name, dose_mg: f.typical.dose_mg, times_per_day: f.typical.times_per_day, duration_days: null, instructions: null, reason: null }]);
    else if (custom.trim()) { setRows((p) => [...p, { drug_key: custom.trim().toLowerCase().replace(/[^a-z0-9]+/g, "_").slice(0, 40) || "custom", drug_name: custom.trim(), dose_mg: null, times_per_day: null, duration_days: null, instructions: null, reason: null }]); setCustom(""); }
    setDirty(true);
  };

  if (rxQ.isLoading) return <LoadingBlock rows={4} />;
  if (rxQ.error) return <ErrorState error={rxQ.error} onRetry={() => rxQ.refetch()} />;
  if (!rx) return null;
  const snap = rx.snapshot ?? {};
  const blocking = (safety?.warnings ?? []).filter((w) => w.severity === "block");

  return (
    <>
      <Link to="/doctor/queue" className="btn-ghost mb-2"><ArrowLeft className="h-4 w-4" />{t("app.back")}</Link>
      <PageHeader title={`#${rx.id} · ${rx.patient.name}`} subtitle={`${fmtDate(rx.created_at, i18n.language)}`}
        right={<Chip tone={rx.status === "signed" ? "ok" : rx.status === "submitted" ? "info" : rx.status === "rejected" ? "danger" : "slate"} className="!text-sm">{t(`rx.status.${rx.status}`)}</Chip>} />
      <div className="grid gap-6 xl:grid-cols-[280px_minmax(0,1fr)_340px]">
        <Card className="h-fit space-y-3">
          <Link to={`/doctor/patients/${rx.patient.id}`} className="block font-bold text-accent hover:underline">{rx.patient.name}</Link>
          <div className="grid grid-cols-2 gap-2 text-sm">
            {([["eGFR", snap.egfr], ["Stage", snap.g_stage], ["ACR", snap.acr], ["K+", snap.potassium], ["SBP", snap.sbp], ["HbA1c", snap.hba1c], ["Hb", snap.hgb], ["Age", snap.age]] as const).map(([k, v]) => (
              <div key={k} className="rounded-xl bg-slate-50 p-2"><p className="text-xs text-muted">{k}</p><p className="font-bold">{typeof v === "number" ? fmtNumber(v, i18n.language) : v ?? "-"}</p></div>
            ))}
          </div>
          {snap.egfr !== undefined && snap.egfr !== null && <KidneyFromSnapshot snap={snap} />}
        </Card>

        <div className="space-y-4">
          <Card>
            <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
              <h2 className="text-lg font-bold">{t("rx.medicines")}</h2>
              {editable && <div className="flex gap-2">
                <select className="input !w-auto" value="" onChange={(e) => e.target.value && addDrug(e.target.value)} data-testid="add-drug" aria-label={t("doctor.addItem")}>
                  <option value="">+ {t("doctor.addItem")}</option>
                  {Object.entries(formQ.data ?? {}).map(([k, f]) => <option key={k} value={k}>{f.name} ({f.class.replace(/_/g, " ")})</option>)}
                </select>
              </div>}
            </div>
            {rows.length === 0 && <p className="text-muted">{t("rx.noMedicines")}</p>}
            <div className="space-y-3">
              {rows.map((r, i) => (
                <div key={i} className="rounded-xl2 border border-line p-3" data-testid="drug-row">
                  <div className="flex items-start justify-between gap-2"><p className="font-bold">{r.drug_name}{" "}{r.suggested_by_system && <Chip tone="info" className="ml-1">{t("doctor.suggested")}</Chip>}</p>
                    {editable && <button className="btn-ghost !min-h-[36px] !px-2 text-danger" aria-label={t("app.delete")} onClick={() => { setRows((p) => p.filter((_, n) => n !== i)); setDirty(true); }}><Trash2 className="h-4 w-4" /></button>}</div>
                  {r.reason && <p className="mb-2 flex gap-1 text-xs text-muted"><Info className="h-3.5 w-3.5 shrink-0" />{r.reason}</p>}
                  <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
                    <Field label={t("doctor.doseMg")}><input data-testid={`dose-${i}`} disabled={!editable} type="number" step="any" className="input" value={r.dose_mg ?? ""} onChange={(e) => update(i, { dose_mg: e.target.value === "" ? null : Number(e.target.value) })} /></Field>
                    <Field label={t("doctor.timesPerDay")}><input data-testid={`times-${i}`} disabled={!editable} type="number" step="any" className="input" value={r.times_per_day ?? ""} onChange={(e) => update(i, { times_per_day: e.target.value === "" ? null : Number(e.target.value) })} /></Field>
                    <Field label={t("doctor.days")}><input disabled={!editable} type="number" className="input" value={r.duration_days ?? ""} onChange={(e) => update(i, { duration_days: e.target.value === "" ? null : Number(e.target.value) })} /></Field>
                    <Field label={t("doctor.instructions")}><input disabled={!editable} className="input" value={r.instructions ?? ""} onChange={(e) => update(i, { instructions: e.target.value || null })} /></Field>
                  </div>
                </div>
              ))}
            </div>
            {editable && (
              <div className="mt-3 flex flex-wrap items-end gap-2">
                <Field label={t("doctor.customDrug")}><input className="input" value={custom} onChange={(e) => setCustom(e.target.value)} /></Field>
                <button className="btn-outline" onClick={() => addDrug("")} disabled={!custom.trim()}><Plus className="h-4 w-4" />{t("doctor.addItem")}</button>
                <button className="btn-soft ml-auto" onClick={() => save.mutate()} disabled={!dirty || save.isPending} data-testid="save-items">{save.isPending ? <Spinner /> : t("app.save")}</button>
              </div>
            )}
          </Card>

          <Card>
            <Field label={t("doctor.notes")}><textarea className="input min-h-[80px]" disabled={!editable} value={notes} maxLength={2000} onChange={(e) => setNotes(e.target.value)} data-testid="notes" /></Field>
            {rx.status === "rejected" && rx.reject_reason && <p className="mt-2 text-sm text-muted">{rx.reject_reason}</p>}
            {rx.override_reason && <p className="mt-2 rounded-xl bg-amber-50 p-2 text-sm">Override: {rx.override_reason}</p>}
            <div className="mt-4 flex flex-wrap gap-2">
              {editable && <>
                <button className="btn-primary" disabled={sign.isPending || dirty} onClick={() => sign.mutate(undefined)} data-testid="sign">{sign.isPending ? <Spinner className="text-white" /> : <><ShieldCheck className="h-4 w-4" />{t("doctor.sign")}</>}</button>
                <button className="btn-outline" onClick={() => setRejectOpen(true)} data-testid="reject">{t("doctor.reject")}</button>
                {dirty && <span className="self-center text-sm text-amber-700">{t("app.save")}…</span>}
              </>}
              {rx.status === "signed" && <>
                <button className="btn-primary" onClick={() => api.rxOpenPdf(rid).catch((e) => notify.error(e))}><Download className="h-4 w-4" />{t("rx.download")}</button>
                <button className="btn-outline" onClick={() => api.rxOpenPrintable(rid, currentLang()).catch((e) => notify.error(e))}><Printer className="h-4 w-4" />{t("rx.printable")}</button>
                <button className="btn-outline" onClick={() => revise.mutate()} data-testid="revise"><FilePlus2 className="h-4 w-4" />{t("doctor.revise")}</button>
              </>}
            </div>
          </Card>

          {rx.care_plan?.sections && (
            <details className="card p-4"><summary className="cursor-pointer font-bold">{t("carePlan.title")}</summary>
              <div className="mt-3 space-y-3">{Object.entries(rx.care_plan.sections).filter(([, v]) => v.length).map(([sec, items]) => <div key={sec}><p className="text-xs font-bold uppercase text-muted">{t(`carePlan.sections.${sec}`)}</p><ul className="list-disc pl-5 text-sm">{items.map((it) => <li key={it.code}>{it.text_en}</li>)}</ul></div>)}</div>
            </details>
          )}
        </div>

        <Card className="h-fit space-y-3" data-testid="safety-panel">
          <div className="flex items-center justify-between"><h2 className="text-lg font-bold">{t("doctor.safetyCheck")}</h2>
            <button className="btn-outline !min-h-[36px] text-sm" onClick={() => check.mutate()} disabled={check.isPending}>{check.isPending ? <Spinner /> : "↻"}</button></div>
          {safety && (safety.ok_to_sign ? <p className="rounded-xl bg-emerald-50 p-2 font-semibold text-emerald-800" data-testid="safety-ok">{t("doctor.okToSign")}</p> : <p className="rounded-xl bg-rose-50 p-2 font-semibold text-rose-800" data-testid="safety-blocked">{tx(t, "doctor.blocking", { n: safety.blocking })}</p>)}
          <ul className="space-y-2">
            {(safety?.warnings ?? []).map((w, i) => (
              <li key={i} className={`rounded-xl border p-2 text-sm ${w.severity === "block" ? "border-rose-300 bg-rose-50" : w.severity === "warn" ? "border-amber-300 bg-amber-50" : "border-blue-200 bg-blue-50"}`} data-testid={`warn-${w.code}`}>
                <Chip tone={w.severity === "block" ? "danger" : w.severity === "warn" ? "warn" : "info"}>{t(`doctor.severity.${w.severity}`)}</Chip>
                <p className="mt-1">{w.text_en}</p>
              </li>
            ))}
          </ul>
          {safety?.note && <p className="text-xs text-muted">{t("doctor.rulesNote")}</p>}
        </Card>
      </div>

      <Modal open={!!override} onClose={() => setOverride(null)} title={t("doctor.overrideTitle")} description={t("doctor.overrideHelp")}>
        <ul className="mb-3 space-y-2">{(override?.safety.warnings ?? []).filter((w) => w.severity === "block").map((w, i) => <li key={i} className="flex gap-2 rounded-xl bg-rose-50 p-2 text-sm"><AlertTriangle className="h-4 w-4 shrink-0 text-danger" />{w.text_en}</li>)}</ul>
        <Field label={t("doctor.overrideReason")}><textarea data-testid="override-reason" className="input min-h-[90px]" value={reason} onChange={(e) => setReason(e.target.value)} /></Field>
        <div className="mt-4 flex justify-end gap-2"><button className="btn-outline" onClick={() => setOverride(null)}>{t("app.cancel")}</button>
          <button className="btn-danger" disabled={reason.trim().length < 10 || sign.isPending} onClick={() => sign.mutate(reason.trim())} data-testid="sign-anyway">{t("doctor.signAnyway")}</button></div>
      </Modal>
      <Modal open={rejectOpen} onClose={() => setRejectOpen(false)} title={t("doctor.reject")}>
        <Field label={t("doctor.rejectReason")}><textarea data-testid="reject-reason" className="input min-h-[90px]" value={rejectReason} onChange={(e) => setRejectReason(e.target.value)} /></Field>
        <div className="mt-4 flex justify-end gap-2"><button className="btn-outline" onClick={() => setRejectOpen(false)}>{t("app.cancel")}</button><button className="btn-primary" disabled={rejectReason.trim().length < 5} onClick={() => reject.mutate()} data-testid="confirm-reject">{t("doctor.reject")}</button></div>
      </Modal>
      {blocking.length > 0 && <span className="sr-only">{blocking.length}</span>}
    </>
  );
}

function KidneyFromSnapshot({ snap }: { snap: Record<string, any> }) {
  const { data } = useQuery({
    queryKey: ["kidney-snap", snap.egfr, snap.acr, snap.sbp, snap.hgb, snap.potassium],
    queryFn: () => api.kidneyState({ egfr: snap.egfr, acr: snap.acr ?? undefined, sbp: snap.sbp ?? undefined, hgb: snap.hgb ?? undefined, potassium: snap.potassium ?? undefined, sex: snap.sex ?? undefined }),
  });
  return data ? <LivingKidney state={data} size="sm" showEcg={false} /> : null;
}
