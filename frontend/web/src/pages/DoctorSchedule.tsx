import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CalendarCheck, Check, MessageCircle, X } from "lucide-react";
import { useMemo } from "react";
import { Link } from "react-router-dom";
import { Card, Chip, EmptyState, ErrorState, LoadingBlock, PageHeader, useNotify } from "@/components/ui";
import { api, type Appointment } from "@/lib/api";
import { fmtDate, fmtTime } from "@/lib/utils";

function Row({ a, act }: { a: Appointment; act?: (id: number, s: "confirmed" | "cancelled") => void }) {
  return (
    <li className="flex flex-wrap items-center gap-3 rounded-xl border border-line p-3" data-testid="appt-row">
      <div className="w-16 text-center"><p className="text-xs font-semibold uppercase text-muted">{fmtDate(a.starts_at, "en", { month: "short" })}</p><p className="text-2xl font-extrabold leading-none">{new Date(a.starts_at).getDate()}</p><p className="text-xs text-muted">{fmtTime(a.starts_at, "en")}</p></div>
      <div className="min-w-0 flex-1"><Link to={`/doctor/patients/${a.patient.id}`} className="font-semibold hover:underline">{a.patient.name}</Link><p className="truncate text-sm text-muted">{a.note || "Consultation"}{a.provider ? ` · ${a.provider.name}` : ""}</p></div>
      <Chip tone={a.status === "confirmed" ? "ok" : a.status === "requested" ? "warn" : "slate"}>{a.status}</Chip>
      {act && a.status === "requested" && <button className="btn-primary !min-h-[36px] text-sm" onClick={() => act(a.id, "confirmed")}><Check className="h-4 w-4" />Confirm</button>}
      {act && a.status !== "cancelled" && <button className="btn-outline !min-h-[36px] text-sm" onClick={() => act(a.id, "cancelled")}><X className="h-4 w-4" />Cancel</button>}
    </li>
  );
}

export default function DoctorSchedule() {
  const qc = useQueryClient();
  const notify = useNotify();
  const q = useQuery({ queryKey: ["care-hub", "appointments"], queryFn: () => api.appointments(), refetchInterval: 30000 });
  const set = useMutation({ mutationFn: (v: { id: number; s: "confirmed" | "cancelled" }) => api.setAppointmentStatus(v.id, v.s), onSuccess: () => void qc.invalidateQueries({ queryKey: ["care-hub"] }), onError: (e) => notify.error(e) });
  const groups = useMemo(() => {
    const now = Date.now(), all = (q.data ?? []).slice().sort((a, b) => +new Date(a.starts_at) - +new Date(b.starts_at));
    const day = new Date(); day.setHours(23, 59, 59, 999);
    return { requests: all.filter((a) => a.status === "requested" && +new Date(a.starts_at) >= now), today: all.filter((a) => a.status !== "cancelled" && +new Date(a.starts_at) >= now && +new Date(a.starts_at) <= +day), upcoming: all.filter((a) => a.status !== "cancelled" && +new Date(a.starts_at) > +day), past: all.filter((a) => +new Date(a.starts_at) < now).reverse().slice(0, 10) };
  }, [q.data]);
  if (q.isLoading) return <LoadingBlock rows={4} />;
  if (q.error) return <ErrorState error={q.error} onRetry={() => q.refetch()} />;
  const act = (id: number, s: "confirmed" | "cancelled") => set.mutate({ id, s });
  const block = (title: string, rows: Appointment[], withAct = true) => rows.length > 0 && <Card><h2 className="mb-3 font-semibold">{title} <span className="text-muted">({rows.length})</span></h2><ul className="space-y-2">{rows.map((a) => <Row key={a.id} a={a} act={withAct ? act : undefined} />)}</ul></Card>;
  const empty = !q.data?.length;
  return (
    <div className="space-y-5" data-testid="doctor-schedule">
      <PageHeader title="Schedule" subtitle="Appointment requests from your patients. Confirm or cancel; patients are notified." />
      {empty ? <EmptyState title="No appointments yet" body="Patients can request a visit with you from their Care hub." icon={<CalendarCheck className="h-7 w-7" />} action={<Link to="/chat" className="btn-soft"><MessageCircle className="h-4 w-4" />Open messages</Link>} /> : (
        <>{block("Waiting for your answer", groups.requests)}{block("Today", groups.today)}{block("Upcoming", groups.upcoming)}{block("Recent", groups.past, false)}</>
      )}
    </div>
  );
}
