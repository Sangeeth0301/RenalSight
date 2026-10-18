import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { BadgeCheck } from "lucide-react";
import { Link } from "react-router-dom";
import { Card, Chip, EmptyState, ErrorState, LoadingBlock, PageHeader, useNotify } from "@/components/ui";
import { api } from "@/lib/api";
import { fmtDate } from "@/lib/utils";

/** Coordinator desk (doctors and admins, English only): review every open request and verify the genuine ones. */
export default function Desk() {
  const qc = useQueryClient();
  const notify = useNotify();
  const q = useQuery({ queryKey: ["tx", "desk"], queryFn: () => api.requests(true) });
  const verify = useMutation({ mutationFn: (id: number) => api.verifyRequest(id), onSuccess: () => { notify.ok("Verified"); void qc.invalidateQueries({ queryKey: ["tx"] }); }, onError: (e) => notify.error(e) });
  if (q.isLoading) return <LoadingBlock rows={4} />;
  if (q.error) return <ErrorState error={q.error} onRetry={() => void q.refetch()} />;
  return (
    <div className="space-y-5">
      <PageHeader title="Coordinator desk" subtitle="Confirm with the hospital that the patient and request are genuine before verifying. Verified requests show a badge on the public page." right={<Link to="/hub/hospitals" className="btn-soft">Dialysis seats</Link>} />
      {!q.data?.length ? <EmptyState title="No requests yet" /> : (
        <div className="space-y-3" data-testid="desk-list">
          {q.data.map((r) => (
            <Card key={r.id} className="flex flex-wrap items-center gap-3">
              <div className="min-w-0 flex-1"><p className="font-semibold">{r.patient_name} · {r.blood_group} · {r.organ}</p><p className="truncate text-sm text-muted">{r.hospital_name} · {r.city} · {fmtDate(r.created_at, "en")} · contact {r.contact_name} {r.contact_phone}</p></div>
              <Chip tone={r.urgency === "urgent" ? "danger" : "slate"}>{r.urgency}</Chip><Chip tone="info">{r.status}</Chip>
              {r.verified ? <Chip tone="ok"><BadgeCheck className="h-3 w-3" />Verified</Chip> : <button className="btn-soft !min-h-[36px] text-sm" onClick={() => verify.mutate(r.id!)}>Verify</button>}
              <Link className="btn-ghost !min-h-[36px] text-sm" to={`/hub/request/${r.id}`}>Open</Link>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
