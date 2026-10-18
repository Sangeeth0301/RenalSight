import { Tx } from "@/lib/translate";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Bell, Bot, Check, ClipboardList, MessageCircle, RefreshCw, Sparkles, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import { Card, Chip, EmptyState, ErrorState, LoadingBlock, PageHeader, Spinner, useNotify } from "@/components/ui";
import { api, type AgentTask } from "@/lib/api";
import { fmtDate, relTime, tx } from "@/lib/utils";
import { useSession } from "@/store/session";

/** Patient-facing tasks are rendered from the translated keys (the server text is English). */
function patientText(t: AgentTask, tr: (k: string, o?: any) => string): { title: string; body: string } {
  const p = t.payload ?? {};
  switch (t.kind) {
    case "lab_due": return p.late_days > 0 ? { title: tr("inbox.patient.lab_overdue.title"), body: tr("inbox.patient.lab_overdue.body", { due: p.due }) } : { title: tr("inbox.patient.lab_due.title"), body: tr("inbox.patient.lab_due.body", { due: p.due }) };
    case "stage_change": return p.worse ? { title: tr("inbox.patient.stage_change_worse.title"), body: tr("inbox.patient.stage_change_worse.body", { from: p.from, to: p.to }) } : { title: tr("inbox.patient.stage_change_better.title"), body: tr("inbox.patient.stage_change_better.body", { from: p.from, to: p.to }) };
    case "missed_meds": return { title: tr("inbox.patient.missed_meds.title"), body: tr("inbox.patient.missed_meds.body") };
    case "rx_request": return { title: tr("inbox.patient.rx_request.title"), body: tr("inbox.patient.rx_request.body") };
    default: return { title: t.title, body: t.body };
  }
}

export default function Inbox() {
  const { t, i18n } = useTranslation();
  const qc = useQueryClient();
  const notify = useNotify();
  const user = useSession((s) => s.user)!;
  const isPatient = user.role === "patient";
  const q = useQuery({ queryKey: ["inbox"], queryFn: () => api.inbox(), refetchInterval: 30000 });
  const [edits, setEdits] = useState<Record<number, string>>({});
  const [created, setCreated] = useState<Record<number, number>>({});

  const refresh = useMutation({
    mutationFn: () => api.agentsRefresh(),
    onSuccess: async (r) => { const n = Object.values(r.created).reduce((a, b) => a + b, 0); notify.ok(n ? tx(t, "inbox.created", { n }) : t("inbox.nothingNew")); await qc.invalidateQueries({ queryKey: ["inbox"] }); void qc.invalidateQueries({ queryKey: ["notifications"] }); },
    onError: (e) => notify.error(e),
  });
  const checked = useRef(false);
  useEffect(() => { if (!checked.current) { checked.current = true; refresh.mutate(); } /* check once when the page opens */ }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const act = useMutation({
    mutationFn: async (v: { id: number; op: "approve" | "reject" | "dismiss"; text?: string }) => {
      if (v.op === "approve") return api.approveTask(v.id, v.text);
      if (v.op === "reject") return { task: await api.rejectTask(v.id) };
      return { task: await api.dismissTask(v.id) };
    },
    onSuccess: async (r: any, v) => { if (r.rx_id) setCreated((c) => ({ ...c, [v.id]: r.rx_id })); await qc.invalidateQueries({ queryKey: ["inbox"] }); void qc.invalidateQueries({ queryKey: ["rx"] }); void qc.invalidateQueries({ queryKey: ["threads"] }); },
    onError: (e) => notify.error(e),
  });

  if (q.isLoading) return <LoadingBlock />;
  if (q.error) return <ErrorState error={q.error} onRetry={() => q.refetch()} />;
  const all = q.data ?? [];
  const pending = all.filter((x) => x.status === "pending");
  const history = all.filter((x) => x.status !== "pending");

  const card = (task: AgentTask) => {
    const txt = isPatient ? patientText(task, t as any) : { title: task.title, body: task.body };
    const plan = task.kind === "camp_plan" ? task.payload : null;
    const msg = task.kind === "doctor_message";
    return (
      <Card key={task.id} className={task.status === "pending" && task.requires_approval ? "border-accent/50" : ""} data-testid="task">
        <div className="flex flex-wrap items-start gap-3">
          <span className="grid h-10 w-10 shrink-0 place-items-center rounded-full bg-accent-soft text-accent">{msg ? <MessageCircle className="h-5 w-5" /> : plan ? <ClipboardList className="h-5 w-5" /> : task.agent === "buddy" ? <Bot className="h-5 w-5" /> : <Bell className="h-5 w-5" />}</span>
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center gap-2"><p className="font-bold" data-testid="task-title">{txt.title}</p><Chip tone={task.status === "pending" ? "warn" : task.status === "approved" ? "ok" : "slate"}>{t(`inbox.status.${task.status}`)}</Chip></div>
            {!msg && <Tx as="p" className="mt-1 text-sm" text={txt.body} />}
            <p className="mt-1 text-xs text-muted">{task.agent} · {relTime(task.created_at, i18n.language)}</p>
            {msg && (task.status === "pending" ? <>
              <label className="label mt-2">{t("doctor.editMessage")}</label>
              <textarea data-testid="msg-edit" className="input min-h-[110px]" value={edits[task.id] ?? task.payload.text ?? ""} onChange={(e) => setEdits({ ...edits, [task.id]: e.target.value })} maxLength={1500} />
            </> : <p className="mt-2 rounded-xl bg-slate-50 p-3 text-sm">{task.payload.text}</p>)}
            {plan && (
              <div className="mt-2 space-y-2 rounded-xl bg-slate-50 p-3 text-sm" data-testid="camp-plan">
                <p><b>{plan.region_name}</b>: {plan.camp_days} camp day(s), {plan.target_people} people, about {plan.expected_with_kidney_disease} expected with kidney disease.</p>
                <ul className="list-disc pl-5">{(plan.checklist as string[]).map((c) => <li key={c}>{c}</li>)}</ul>
                <p className="text-xs text-muted">{(plan.assumptions as string[]).join(" ")}</p>
              </div>
            )}
            {task.kind === "rx_request" && (task.status === "approved" || created[task.id]) && <p className="mt-2 rounded-xl bg-emerald-50 p-2 text-sm text-emerald-800">{t("inbox.rxCreated")} <Link className="font-semibold underline" to="/rx">{t("nav.rxStudio")}</Link></p>}
          </div>
          {task.status === "pending" && (
            <div className="flex shrink-0 flex-wrap gap-2">
              {task.requires_approval ? <>
                <button className="btn-primary !min-h-[40px]" disabled={act.isPending} onClick={() => act.mutate({ id: task.id, op: "approve", text: msg ? edits[task.id] : undefined })} data-testid="approve"><Check className="h-4 w-4" />{msg ? t("doctor.approveSend") : t("inbox.approve")}</button>
                <button className="btn-outline !min-h-[40px]" disabled={act.isPending} onClick={() => act.mutate({ id: task.id, op: "reject" })} data-testid="reject-task"><X className="h-4 w-4" />{t("inbox.reject")}</button>
              </> : <button className="btn-outline !min-h-[40px]" onClick={() => act.mutate({ id: task.id, op: "dismiss" })} data-testid="dismiss">{t("inbox.dismiss")}</button>}
            </div>
          )}
        </div>
      </Card>
    );
  };

  return (
    <>
      <PageHeader title={t("inbox.title")} subtitle={t("inbox.subtitle")} right={<button className="btn-outline" onClick={() => refresh.mutate()} disabled={refresh.isPending} data-testid="refresh-inbox">{refresh.isPending ? <Spinner /> : <RefreshCw className="h-4 w-4" />}{t("inbox.refresh")}</button>} />
      {all.length === 0 ? <EmptyState title={t("inbox.empty")} icon={<Sparkles className="h-7 w-7" />} /> : (
        <div className="space-y-6">
          {pending.length > 0 && <section><h2 className="mb-3 text-lg font-bold">{t("inbox.pending")} ({pending.length})</h2><div className="space-y-3" data-testid="pending-tasks">{pending.map(card)}</div></section>}
          {history.length > 0 && <section><h2 className="mb-3 text-lg font-bold">{t("inbox.history")}</h2><div className="space-y-3 opacity-80">{history.slice(0, 20).map(card)}</div></section>}
        </div>
      )}
      <p className="mt-6 text-center text-xs text-muted">{fmtDate(new Date().toISOString(), i18n.language)}</p>
    </>
  );
}
