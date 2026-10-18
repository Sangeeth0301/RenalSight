import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Trash2 } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Card, EmptyState, ErrorState, Field, LoadingBlock, PageHeader, useNotify } from "@/components/ui";
import { api } from "@/lib/api";
import { todayISO } from "@/lib/utils";

export default function Dialysis() {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const notify = useNotify();
  const q = useQuery({ queryKey: ["tx", "dialysis"], queryFn: () => api.dialysis() });
  const [f, setF] = useState({ on_date: todayISO(), centre: "", pre_weight: "", post_weight: "", pre_bp: "", post_bp: "", hours: "4" });
  const num = (v: string) => (v ? Number(v) : null);
  const add = useMutation({
    mutationFn: () => api.addDialysis({ on_date: f.on_date, centre: f.centre, pre_weight: num(f.pre_weight), post_weight: num(f.post_weight), pre_bp: f.pre_bp, post_bp: f.post_bp, hours: num(f.hours) }),
    onSuccess: () => { notify.ok(t("transplant.sessionSaved", "Session saved")); void qc.invalidateQueries({ queryKey: ["tx", "dialysis"] }); },
    onError: (e) => notify.error(e),
  });
  const del = useMutation({ mutationFn: (id: number) => api.deleteDialysis(id), onSuccess: () => void qc.invalidateQueries({ queryKey: ["tx", "dialysis"] }) });
  if (q.isLoading) return <LoadingBlock rows={4} />;
  if (q.error || !q.data) return <ErrorState error={q.error} onRetry={() => void q.refetch()} />;
  const d = q.data;
  const chart = d.interdialytic_gain_kg.map((g, i) => ({ i: d.sessions[i]?.on_date.slice(5) ?? String(i), gain: g })).reverse();
  return (
    <div className="space-y-5">
      <PageHeader title={t("transplant.dialysisTitle", "Dialysis log")} subtitle={t("transplant.dialysisSubtitle", "Write down each session. Gaining 3 kg or more between sessions means too much fluid.")} />
      {d.warning && <div className="card border-rose-300/60 p-4 text-rose-800" role="alert" data-testid="dialysis-warning">{d.warning}</div>}
      <Card>
        <div className="grid gap-3 sm:grid-cols-3 lg:grid-cols-6">
          <Field label={t("transplant.date", "Date")}><input className="input" type="date" value={f.on_date} onChange={(e) => setF({ ...f, on_date: e.target.value })} /></Field>
          <Field label={t("transplant.preWeight", "Weight before (kg)")}><input className="input" inputMode="decimal" value={f.pre_weight} onChange={(e) => setF({ ...f, pre_weight: e.target.value })} data-testid="pre-weight" /></Field>
          <Field label={t("transplant.postWeight", "Weight after (kg)")}><input className="input" inputMode="decimal" value={f.post_weight} onChange={(e) => setF({ ...f, post_weight: e.target.value })} data-testid="post-weight" /></Field>
          <Field label={t("transplant.preBp", "BP before")}><input className="input" placeholder="140/90" value={f.pre_bp} onChange={(e) => setF({ ...f, pre_bp: e.target.value })} /></Field>
          <Field label={t("transplant.postBp", "BP after")}><input className="input" placeholder="120/80" value={f.post_bp} onChange={(e) => setF({ ...f, post_bp: e.target.value })} /></Field>
          <Field label={t("transplant.hours", "Hours")}><input className="input" inputMode="decimal" value={f.hours} onChange={(e) => setF({ ...f, hours: e.target.value })} /></Field>
        </div>
        <div className="mt-3 flex flex-wrap items-end gap-3"><div className="min-w-[220px] flex-1"><Field label={t("transplant.centre", "Dialysis centre")}><input className="input" value={f.centre} onChange={(e) => setF({ ...f, centre: e.target.value })} /></Field></div><button className="btn-primary" disabled={add.isPending} onClick={() => add.mutate()} data-testid="add-session">{t("transplant.addSession", "Add session")}</button></div>
      </Card>
      {chart.length > 0 && (
        <Card><p className="mb-2 font-semibold">{t("transplant.gainChart", "Weight gained between sessions (kg)")}</p>
          <div className="h-48"><ResponsiveContainer><BarChart data={chart}><CartesianGrid strokeDasharray="3 3" /><XAxis dataKey="i" /><YAxis /><Tooltip /><Bar dataKey="gain" fill="var(--accent)" radius={[6, 6, 0, 0]} /></BarChart></ResponsiveContainer></div></Card>
      )}
      {!d.sessions.length ? <EmptyState title={t("transplant.noSessions", "No sessions logged")} /> : (
        <Card className="overflow-x-auto"><table className="w-full min-w-[560px] text-sm"><thead><tr className="text-left text-muted"><th className="py-2">{t("transplant.date", "Date")}</th><th>{t("transplant.centre", "Centre")}</th><th>kg</th><th>BP</th><th>h</th><th /></tr></thead>
          <tbody data-testid="session-rows">{d.sessions.map((s) => (
            <tr key={s.id} className="border-t border-[var(--border)]"><td className="py-2">{s.on_date}</td><td>{s.centre || "-"}</td><td>{s.pre_weight ?? "-"} → {s.post_weight ?? "-"}{s.removed_kg != null && <span className="text-muted"> (−{s.removed_kg})</span>}</td><td>{s.pre_bp || "-"} → {s.post_bp || "-"}</td><td>{s.hours ?? "-"}</td>
              <td><button aria-label="delete" className="text-muted hover:text-danger" onClick={() => del.mutate(s.id)}><Trash2 className="h-4 w-4" /></button></td></tr>
          ))}</tbody></table></Card>
      )}
    </div>
  );
}
