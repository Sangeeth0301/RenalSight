import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, MessageCircle, Plus } from "lucide-react";
import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, useNavigate, useParams } from "react-router-dom";
import { Area, CartesianGrid, ComposedChart, Line, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { LivingKidney } from "@/components/LivingKidney";
import { ChatPane } from "@/components/ChatPane";
import { Card, Chip, ErrorState, LoadingBlock, PageHeader, SeverityMeter, Tabs, useNotify } from "@/components/ui";
import { api } from "@/lib/api";
import { fmtDate, fmtNumber, stageColor } from "@/lib/utils";

export default function DoctorPatient() {
  const { t, i18n } = useTranslation();
  const { id } = useParams();
  const pid = Number(id);
  const nav = useNavigate();
  const notify = useNotify();
  const q = useQuery({ queryKey: ["doctor", "patient", pid], queryFn: () => api.doctorPatient(pid) });
  const rxs = useQuery({ queryKey: ["rx", "list"], queryFn: () => api.rxList() });
  const open = useMutation({ mutationFn: () => api.openDirect(pid), onSuccess: (th) => nav(`/chat/${th.id}`), onError: (e) => notify.error(e) });
  const draft = useMutation({ mutationFn: () => api.rxCreateForPatient(pid), onSuccess: (r) => nav(`/doctor/rx/${r.id}`), onError: (e) => notify.error(e) });

  const qc = useQueryClient();
  const [tab, setTab] = useState<"overview" | "labs" | "rx" | "messages">("overview");
  const threads = useQuery({ queryKey: ["threads"], queryFn: () => api.threads(), enabled: tab === "messages" });
  const thread = (threads.data ?? []).find((x) => x.kind === "direct" && x.members.some((m) => m.id === pid));
  const start = useMutation({ mutationFn: () => api.openDirect(pid), onSuccess: () => void qc.invalidateQueries({ queryKey: ["threads"] }), onError: (e) => notify.error(e) });
  const d = q.data;
  const fc = d?.forecast;
  const data = useMemo(() => (fc?.years ?? []).map((y, i) => ({ year: y, median: fc!.egfr_p50[i], band: [fc!.egfr_p10[i], fc!.egfr_p90[i]] })), [fc]);
  const chart = useMemo(() => (d?.labs ?? []).filter((l) => l.egfr !== null).map((l) => ({ date: l.taken_on, egfr: l.egfr })), [d]);

  if (q.isLoading) return <LoadingBlock rows={4} />;
  if (q.error) return <ErrorState error={q.error} onRetry={() => q.refetch()} />;
  if (!d) return null;
  const s = d.state;
  const snap = d.snapshot;
  const mine = (rxs.data ?? []).filter((r) => r.patient.id === pid);

  return (
    <>
      <Link to="/doctor" className="btn-ghost mb-2"><ArrowLeft className="h-4 w-4" />{t("app.back")}</Link>
      <PageHeader title={d.patient.name} subtitle={`${d.patient.age ?? "-"} / ${d.patient.sex ?? "-"}`} right={
        <div className="flex flex-wrap gap-2">
          <button className="btn-outline" onClick={() => setTab("messages")} data-testid="message-patient"><MessageCircle className="h-4 w-4" />{t("doctor.message")}</button>
          <button className="btn-primary" onClick={() => draft.mutate()} disabled={draft.isPending} data-testid="create-draft"><Plus className="h-4 w-4" />{t("doctor.createDraft")}</button>
        </div>} />
      <Tabs value={tab} onChange={setTab} tabs={[{ value: "overview", label: "Overview" }, { value: "labs", label: `Lab results (${d.labs.length})` }, { value: "rx", label: `Prescriptions (${mine.length})` }, { value: "messages", label: "Messages" }]} />
      {tab === "labs" && (
        <Card className="overflow-x-auto" data-testid="labs-table"><table className="w-full min-w-[640px] text-sm"><thead><tr className="text-left text-xs uppercase text-muted"><th className="py-2">Date</th><th>Cr</th><th>eGFR</th><th>Stage</th><th>ACR</th><th>BP</th><th>HbA1c</th><th>Hb</th><th>K+</th><th>BUN</th></tr></thead>
          <tbody>{[...d.labs].reverse().map((l) => <tr key={l.id} className="border-t border-line"><td className="py-2">{fmtDate(l.taken_on, i18n.language)}</td><td>{l.scr ?? "-"}</td><td className="font-semibold">{l.egfr ?? "-"}</td><td>{l.g_stage ? <span className="chip text-white" style={{ background: stageColor(l.g_stage) }}>{l.g_stage}</span> : "-"}</td><td>{l.acr ?? "-"}</td><td>{l.sbp ?? "-"}{l.dbp ? `/${l.dbp}` : ""}</td><td>{l.hba1c ?? "-"}</td><td>{l.hgb ?? "-"}</td><td>{l.potassium ?? "-"}</td><td>{l.bun ?? "-"}</td></tr>)}</tbody></table>
          {d.labs.length === 0 && <p className="py-6 text-center text-muted">No lab results yet.</p>}</Card>
      )}
      {tab === "rx" && (
        <Card>{mine.length === 0 ? <p className="text-muted">No prescriptions yet. Use "Create draft" to start one.</p> : <ul className="space-y-2">{mine.map((r) => <li key={r.id}><Link to={`/doctor/rx/${r.id}`} className="flex items-center justify-between rounded-xl border border-line p-3 hover:bg-[var(--surface-2)]"><span>Prescription #{r.id} · {fmtDate(r.created_at, i18n.language)}</span><Chip tone={r.status === "signed" ? "ok" : r.status === "submitted" ? "info" : "slate"}>{t(`rx.status.${r.status}`)}</Chip></Link></li>)}</ul>}</Card>
      )}
      {tab === "messages" && (
        <div style={{ height: "calc(100vh - 17rem)", minHeight: 420 }}>
          {threads.isLoading ? <LoadingBlock /> : thread ? <ChatPane key={thread.id} thread={thread} /> : (
            <Card className="grid h-full place-items-center text-center"><div><MessageCircle className="mx-auto mb-2 h-8 w-8 text-accent" /><p className="mb-3 text-muted">No conversation with {d.patient.name} yet.</p><button className="btn-primary" onClick={() => start.mutate()} disabled={start.isPending} data-testid="start-chat">Start conversation</button></div></Card>
          )}
        </div>
      )}
      <div className={tab === "overview" ? "grid gap-6 lg:grid-cols-[360px_minmax(0,1fr)]" : "hidden"}>
        <Card className="flex flex-col items-center">
          {s.has_data ? <><LivingKidney state={s} size="lg" interactive /><div className="mt-3 flex items-center gap-2"><span className="chip text-white" style={{ background: stageColor(s.g_stage) }}>{s.g_stage}</span><Chip tone="accent">{t(`stages.${s.stage_name}`)}</Chip>{s.urgent && <Chip tone="danger">Urgent</Chip>}</div><div className="mt-3 w-full"><SeverityMeter value={s.severity} /></div></>
            : <p className="py-10 text-muted">{s.message ?? t("kidney.noData")}</p>}
        </Card>
        <div className="space-y-6">
          <Card>
            <h2 className="mb-3 text-lg font-bold">{t("doctor.snapshot")} {snap.as_of && <span className="text-sm font-normal text-muted">({fmtDate(snap.as_of, i18n.language)})</span>}</h2>
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
              {([["eGFR", snap.egfr], ["ACR", snap.acr], ["K+", snap.potassium], ["SBP", snap.sbp], ["HbA1c", snap.hba1c], ["Hb", snap.hgb], ["Cr", snap.scr], ["BUN", snap.bun]] as const).map(([k, v]) => (
                <div key={k} className="rounded-xl bg-[var(--surface-3)] p-3"><p className="text-xs text-muted">{k}</p><p className="text-xl font-bold">{fmtNumber(v as number | null, i18n.language)}</p></div>
              ))}
            </div>
          </Card>
          <Card>
            <h2 className="mb-2 text-lg font-bold">{t("doctor.labs")}</h2>
            {chart.length === 0 ? <p className="text-muted">{t("app.noData")}</p> : (
              <div className="h-56"><ResponsiveContainer><ComposedChart data={chart} margin={{ top: 8, right: 12, left: -12, bottom: 0 }}><CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" /><XAxis dataKey="date" tickFormatter={(x) => fmtDate(x, i18n.language, { month: "short", year: "2-digit" })} tick={{ fontSize: 12 }} /><YAxis domain={[0, 120]} tick={{ fontSize: 12 }} /><Tooltip /><ReferenceLine y={15} stroke="#e11d48" strokeDasharray="4 4" /><ReferenceLine y={60} stroke="#94a3b8" strokeDasharray="4 4" /><Line dataKey="egfr" stroke="var(--accent)" strokeWidth={3} dot={{ r: 4 }} /></ComposedChart></ResponsiveContainer></div>
            )}
          </Card>
          {fc?.has_data !== false && fc && (
            <Card>
              <h2 className="mb-2 text-lg font-bold">{t("doctor.forecast")} <Chip tone="info">{t("app.estimate")}</Chip></h2>
              <div className="h-56"><ResponsiveContainer><ComposedChart data={data} margin={{ top: 8, right: 12, left: -12, bottom: 0 }}><CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" /><XAxis dataKey="year" type="number" domain={[0, 15]} tick={{ fontSize: 12 }} /><YAxis domain={[0, 120]} tick={{ fontSize: 12 }} /><Tooltip /><ReferenceLine y={15} stroke="#e11d48" strokeDasharray="4 4" /><Area dataKey="band" stroke="none" fill="var(--accent)" fillOpacity={0.18} /><Line dataKey="median" stroke="var(--accent)" strokeWidth={3} dot={false} /></ComposedChart></ResponsiveContainer></div>
              <div className="mt-3 grid grid-cols-3 gap-3 text-center">
                {([["fast", fc.years_to_stage5_p10], ["expected", fc.years_to_stage5_p50], ["slow", fc.years_to_stage5_p90]] as const).map(([k, v]) => <div key={k} className="rounded-xl bg-[var(--surface-3)] p-2"><p className="text-xs text-muted">{t(`forecast.${k}`)}</p><p className="text-lg font-bold">{v === null ? ">30" : fmtNumber(v, i18n.language)}</p></div>)}
              </div>
              <p className="mt-2 text-xs text-muted">{t("forecast.simNote")} · 2y {Math.round(fc.prob_kf_2y * 100)}% · 5y {Math.round(fc.prob_kf_5y * 100)}% · 10y {Math.round(fc.prob_kf_10y * 100)}%</p>
            </Card>
          )}
          <Card>
            <h2 className="mb-2 text-lg font-bold">{t("rx.title")}</h2>
            {mine.length === 0 ? <p className="text-muted">{t("rx.empty")}</p> : <ul className="space-y-2">{mine.map((r) => <li key={r.id}><Link to={`/doctor/rx/${r.id}`} className="flex items-center justify-between rounded-xl border border-line p-3 hover:bg-[var(--surface-2)]"><span>#{r.id} · {fmtDate(r.created_at, i18n.language)}</span><Chip tone={r.status === "signed" ? "ok" : r.status === "submitted" ? "info" : "slate"}>{t(`rx.status.${r.status}`)}</Chip></Link></li>)}</ul>}
          </Card>
        </div>
      </div>
    </>
  );
}
