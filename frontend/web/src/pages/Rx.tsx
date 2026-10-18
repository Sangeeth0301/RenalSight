import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Download, FileText, Pill, Printer, Send } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, useSearchParams } from "react-router-dom";
import { Card, Chip, Disclaimer, EmptyState, ErrorState, LoadingBlock, Modal, PageHeader, Spinner, useNotify } from "@/components/ui";
import { api, ApiError, type PatientRxItem, type Rx as RxT, type RxItem } from "@/lib/api";
import { currentLang } from "@/i18n";
import { fmtDate, tx } from "@/lib/utils";
import { useSession } from "@/store/session";

const TONE = { draft: "slate", submitted: "info", signed: "ok", rejected: "danger" } as const;
const isFull = (i: RxItem | PatientRxItem): i is RxItem => "drug_name" in i;

export default function Rx() {
  const { t, i18n } = useTranslation();
  const qc = useQueryClient();
  const notify = useNotify();
  const user = useSession((s) => s.user)!;
  const [sp, setSp] = useSearchParams();
  const openId = sp.get("open") ? Number(sp.get("open")) : null;
  const [selected, setSelected] = useState<number | null>(openId);
  const list = useQuery({ queryKey: ["rx", "list"], queryFn: () => api.rxList(), refetchInterval: 30000 });
  const detail = useQuery({ queryKey: ["rx", selected], queryFn: () => api.rx(selected!), enabled: selected !== null });

  const request = useMutation({
    mutationFn: () => api.rxRequest(),
    onSuccess: async (r) => { await qc.invalidateQueries({ queryKey: ["rx"] }); setSelected(r.id); },
    onError: (e) => (e instanceof ApiError && e.status === 422 ? notify.errorText(t("rx.needLabs")) : notify.error(e)),
  });
  const submit = useMutation({
    mutationFn: (id: number) => api.rxSubmit(id),
    onSuccess: async () => { await qc.invalidateQueries({ queryKey: ["rx"] }); notify.ok(t("rx.status.submitted")); },
    onError: (e) => (e instanceof ApiError && e.status === 422 ? notify.errorText(t("rx.needDoctor")) : notify.error(e)),
  });

  const rx = detail.data;
  return (
    <>
      <PageHeader title={t("rx.title")} subtitle={t("rx.requestHelp")} right={<button className="btn-primary" onClick={() => request.mutate()} disabled={request.isPending} data-testid="rx-request">{request.isPending ? <Spinner className="text-white" /> : <><Pill className="h-4 w-4" />{t("rx.request")}</>}</button>} />
      <div className="grid gap-6 lg:grid-cols-[320px_minmax(0,1fr)]">
        <div className="space-y-3">
          {list.isLoading ? <LoadingBlock rows={2} /> : list.error ? <ErrorState error={list.error} onRetry={() => list.refetch()} /> : (list.data ?? []).length === 0 ? (
            <EmptyState title={t("rx.empty")} body={t("rx.requestHelp")} />
          ) : (list.data ?? []).map((r) => (
            <button key={r.id} onClick={() => { setSelected(r.id); setSp({}); }} data-testid="rx-item"
              className={`card w-full p-4 text-left transition hover:shadow-lift ${selected === r.id ? "!border-accent ring-2 ring-accent/30" : ""}`}>
              <div className="flex items-center justify-between"><span className="font-semibold">#{r.id}</span><Chip tone={TONE[r.status]}>{t(`rx.status.${r.status}`)}</Chip></div>
              <p className="mt-1 text-sm text-muted">{fmtDate(r.created_at, i18n.language)}{r.doctor ? ` · Dr. ${r.doctor.name}` : ""}</p>
            </button>
          ))}
        </div>
        <div>
          {selected === null ? <EmptyState title={t("rx.title")} body={t("rx.requestHelp")} icon={<FileText className="h-7 w-7" />} /> : detail.isLoading ? <LoadingBlock /> : detail.error ? <ErrorState error={detail.error} onRetry={() => detail.refetch()} /> : rx && (
            <div className="space-y-4" data-testid="rx-detail">
              <Card>
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div><h2 className="text-xl font-bold">#{rx.id}</h2><p className="text-sm text-muted">{fmtDate(rx.created_at, i18n.language)}</p></div>
                  <Chip tone={TONE[rx.status]} className="!text-sm">{t(`rx.status.${rx.status}`)}</Chip>
                </div>
                <ol className="mt-4 flex items-center gap-2 text-xs font-semibold">
                  {(["draft", "submitted", "signed"] as const).map((s, i) => {
                    const reached = ["draft", "submitted", "signed"].indexOf(rx.status === "rejected" ? "submitted" : rx.status) >= i;
                    return <li key={s} className={`flex-1 rounded-full px-2 py-1 text-center ${reached ? "bg-accent text-white" : "bg-slate-100 text-muted"}`}>{t(`rx.status.${s}`)}</li>;
                  })}
                </ol>
                {rx.status === "rejected" && rx.reject_reason && <p className="mt-3 rounded-xl bg-rose-50 p-3 text-rose-900">{tx(t, "rx.rejectedBecause", { reason: rx.reject_reason })}</p>}
              </Card>

              <Card>
                <h3 className="mb-3 flex items-center gap-2 text-lg font-bold"><Pill className="h-5 w-5 text-accent" />{t("rx.medicines")}</h3>
                {rx.status !== "signed" && rx.items.length > 0 && <p className="mb-3 rounded-xl border border-amber-300 bg-amber-50 p-3 text-amber-900" data-testid="do-not-take">{t("rx.doNotTake")}</p>}
                {rx.items.length === 0 ? <p className="text-muted">{t("rx.noMedicines")}</p> : rx.status === "signed" ? (
                  <div className="overflow-x-auto"><table className="w-full min-w-[480px] text-left text-sm" data-testid="signed-items">
                    <thead className="text-xs uppercase text-muted"><tr><th className="py-2">{t("rx.medicines")}</th><th>{t("rx.dose")}</th><th /><th>#</th><th /></tr></thead>
                    <tbody>{rx.items.filter(isFull).map((i, n) => (
                      <tr key={n} className="border-t border-line"><td className="py-2 font-semibold">{i.drug_name}</td><td>{i.dose_mg} mg</td><td>{i.times_per_day ? tx(t, "rx.perDay", { n: i.times_per_day }) : ""}</td><td>{i.duration_days ?? ""}</td><td className="text-muted">{i.instructions}</td></tr>
                    ))}</tbody></table></div>
                ) : (
                  <ul className="space-y-2">{rx.items.filter((i): i is PatientRxItem => !isFull(i)).map((i, n) => (
                    <li key={n} className="flex items-center justify-between gap-3 rounded-xl border border-line p-3"><span>{i.label}</span><Chip tone="warn">{t("rx.awaitingDoctor")}</Chip></li>
                  ))}</ul>
                )}
                {rx.status === "signed" && <div className="mt-3 space-y-1 text-sm"><p className="font-semibold text-emerald-700">{rx.doctor && tx(t, "rx.signedBy", { name: rx.doctor.name })} · {fmtDate(rx.signed_at, i18n.language)}</p>{rx.doctor_notes && <p>{rx.doctor_notes}</p>}<p className="text-muted">{t("rx.sickDayTip")}</p></div>}
                <div className="mt-4 flex flex-wrap gap-2">
                  {rx.status === "draft" && <button className="btn-primary" onClick={() => submit.mutate(rx.id)} disabled={submit.isPending} data-testid="rx-submit"><Send className="h-4 w-4" />{t("rx.sendToDoctor")}</button>}
                  {rx.status === "draft" && user.doctor_id === null && <Link to="/settings" className="btn-outline">{t("rx.needDoctor")}</Link>}
                  {rx.status === "rejected" && <button className="btn-primary" onClick={() => request.mutate()}>{t("rx.request")}</button>}
                  {rx.status === "signed" && (<>
                    <button className="btn-primary" onClick={() => api.rxOpenPdf(rx.id).catch((e) => notify.error(e))} data-testid="rx-pdf"><Download className="h-4 w-4" />{t("rx.download")}</button>
                    <button className="btn-outline" onClick={() => api.rxOpenPrintable(rx.id, currentLang()).catch((e) => notify.error(e))}><Printer className="h-4 w-4" />{t("rx.printable")}</button>
                  </>)}
                </div>
              </Card>

              {rx.care_plan?.sections && (
                <Card>
                  <h3 className="mb-3 text-lg font-bold">{t("carePlan.title")}</h3>
                  <div className="space-y-4">
                    {Object.entries(rx.care_plan.sections).filter(([, v]) => v.length > 0).map(([sec, items]) => (
                      <div key={sec}><p className="text-xs font-bold uppercase text-muted">{t(`carePlan.sections.${sec}`)}</p>
                        <ul className="mt-1 list-disc space-y-1 pl-5">{items.map((it) => <li key={it.code}>{tx(t, `carePlan.items.${it.code}`, it.params)}</li>)}</ul></div>
                    ))}
                  </div>
                </Card>
              )}
            </div>
          )}
        </div>
      </div>
      <Disclaimer />
    </>
  );
}
