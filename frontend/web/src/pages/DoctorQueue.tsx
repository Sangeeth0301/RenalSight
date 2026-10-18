import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CalendarCheck, ClipboardCheck } from "lucide-react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import { Card, Chip, EmptyState, ErrorState, LoadingBlock, PageHeader, useNotify } from "@/components/ui";
import { api } from "@/lib/api";
import { fmtTime, tx } from "@/lib/utils";

export default function DoctorQueue() {
  const { t, i18n } = useTranslation();
  const q = useQuery({ queryKey: ["doctor", "queue"], queryFn: () => api.doctorQueue(), refetchInterval: 20000 });
  const qc = useQueryClient();
  const notify = useNotify();
  const appts = useQuery({ queryKey: ["care-hub", "appointments"], queryFn: () => api.appointments(), refetchInterval: 30000 });
  const setStatus = useMutation({ mutationFn: (v: { id: number; s: "confirmed" | "cancelled" }) => api.setAppointmentStatus(v.id, v.s), onSuccess: () => void qc.invalidateQueries({ queryKey: ["care-hub"] }), onError: (e) => notify.error(e) });
  return (
    <>
      <PageHeader title={t("doctor.queue")} />
      {q.isLoading ? <LoadingBlock /> : q.error ? <ErrorState error={q.error} onRetry={() => q.refetch()} /> : (q.data ?? []).length === 0 ? <EmptyState title={t("doctor.queueEmpty")} icon={<ClipboardCheck className="h-7 w-7" />} /> : (
        <div className="grid gap-3 sm:grid-cols-2" data-testid="queue">
          {(q.data ?? []).map((r) => (
            <Link key={r.id} to={`/doctor/rx/${r.id}`} className="card p-4 transition hover:shadow-lift" data-testid="queue-item">
              <div className="flex items-center justify-between"><p className="font-bold">{r.patient.name}</p><span className="text-sm text-muted">#{r.id}</span></div>
              <p className="text-sm text-muted">{r.submitted_at ? fmtTime(r.submitted_at, i18n.language) : ""} · {r.items.length} {t("rx.medicines")}</p>
              <div className="mt-2">{r.safety?.ok_to_sign ? <Chip tone="ok">{t("doctor.okToSign")}</Chip> : <Chip tone="danger">{tx(t, "doctor.blocking", { n: r.safety?.blocking ?? 0 })}</Chip>}</div>
            </Link>
          ))}
        </div>
      )}
      <h2 className="mb-3 mt-8 flex items-center gap-2 text-lg font-bold"><CalendarCheck className="h-5 w-5 text-accent" />{t("hub.mine")}</h2>
      {(appts.data ?? []).length === 0 ? <p className="text-muted">{t("hub.none")}</p> : (
        <div className="space-y-2" data-testid="doctor-appointments">
          {appts.data!.map((a) => (
            <Card key={a.id} className="flex flex-wrap items-center justify-between gap-3 !p-4">
              <div><Link to={`/doctor/patients/${a.patient.id}`} className="font-semibold text-accent hover:underline">{a.patient.name}</Link><p className="text-sm text-muted">{fmtTime(a.starts_at, i18n.language)}{a.note ? ` · ${a.note}` : ""}</p></div>
              <div className="flex items-center gap-2"><Chip tone={a.status === "confirmed" ? "ok" : a.status === "cancelled" ? "slate" : "warn"}>{t(`hub.status.${a.status}`)}</Chip>
                {a.status === "requested" && <button className="btn-primary !min-h-[36px] text-sm" onClick={() => setStatus.mutate({ id: a.id, s: "confirmed" })} data-testid="confirm-appt">{t("hub.status.confirmed")}</button>}
                {a.status !== "cancelled" && <button className="btn-outline !min-h-[36px] text-sm" onClick={() => setStatus.mutate({ id: a.id, s: "cancelled" })}>{t("hub.cancel")}</button>}</div>
            </Card>
          ))}
        </div>
      )}
    </>
  );
}
