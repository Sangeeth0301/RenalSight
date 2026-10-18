import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { BadgeCheck, MessageSquareHeart, Phone } from "lucide-react";
import { useTranslation } from "react-i18next";
import { useParams } from "react-router-dom";
import { QR } from "@/components/QR";
import { ShareStudio } from "@/components/ShareStudio";
import { Card, Chip, ErrorState, LoadingBlock, PageHeader, useNotify } from "@/components/ui";
import { api } from "@/lib/api";
import { fmtDate } from "@/lib/utils";
import { useSession } from "@/store/session";

export default function RequestDetail() {
  const { t, i18n } = useTranslation();
  const { id } = useParams();
  const rid = Number(id);
  const qc = useQueryClient();
  const notify = useNotify();
  const user = useSession((s) => s.user)!;
  const staff = user.role === "doctor" || user.role === "admin";
  const q = useQuery({ queryKey: ["tx", "request", rid], queryFn: () => api.request(rid) });
  const refresh = () => void qc.invalidateQueries({ queryKey: ["tx"] });
  const status = useMutation({ mutationFn: (s: string) => api.setRequestStatus(rid, s), onSuccess: refresh, onError: (e) => notify.error(e) });
  const verify = useMutation({ mutationFn: () => api.verifyRequest(rid), onSuccess: () => { notify.ok("Verified"); refresh(); }, onError: (e) => notify.error(e) });
  const offer = useMutation({ mutationFn: (v: { id: number; s: string }) => api.setOfferStatus(v.id, v.s), onSuccess: refresh, onError: (e) => notify.error(e) });
  const contact = useMutation({ mutationFn: (pid: number) => api.contactDonor(rid, pid), onSuccess: () => notify.ok(t("transplant.donorNotified", "The donor was told and can reply to you.")), onError: (e) => notify.error(e) });

  if (q.isLoading) return <LoadingBlock rows={5} />;
  if (q.error || !q.data) return <ErrorState error={q.error} onRetry={() => void q.refetch()} />;
  const r = q.data;
  const url = `${window.location.origin}/r/${r.token}`;

  return (
    <>
      <div className="space-y-6 print:hidden">
        <PageHeader title={`${r.patient_name} · ${r.blood_group}`} subtitle={`${r.hospital_name}${r.city ? ", " + r.city : ""} · ${fmtDate(r.created_at, i18n.language)}`}
          chip={<>{r.verified && <Chip tone="ok"><BadgeCheck className="h-3 w-3" />{t("transplant.verified", "Verified")}</Chip>}<Chip tone={r.status === "open" ? "info" : "slate"}>{r.status}</Chip></>}
          right={<div className="flex flex-wrap gap-2">
            {staff && !r.verified && <button className="btn-soft" onClick={() => verify.mutate()} data-testid="verify">{t("transplant.verify", "Verify request")}</button>}
            <select className="input !w-auto" value={r.status} onChange={(e) => status.mutate(e.target.value)} aria-label="status">
              {["open", "matched", "fulfilled", "closed"].map((s) => <option key={s}>{s}</option>)}
            </select></div>} />

        <Card>
          <h2 className="mb-4 font-display text-lg font-bold">{t("transplant.shareTitle", "Share this request")}</h2>
          <ShareStudio ready requestId={rid} publicUrl={url} input={{ hospital: r.hospital_name, patient_name: r.patient_name, blood_group: r.blood_group }} />
        </Card>

        <div className="grid gap-4 lg:grid-cols-2">
          <Card>
            <h2 className="mb-3 flex items-center gap-2 font-display text-lg font-bold"><MessageSquareHeart className="h-5 w-5 text-accent" />{t("transplant.offersTitle", "People who offered to be tested")}</h2>
            {!r.offer_list.length ? <p className="text-muted">{t("transplant.noOffers", "No offers yet. Share the message and the public link.")}</p> : (
              <ul className="space-y-3" data-testid="offers">
                {r.offer_list.map((o) => (
                  <li key={o.id} className="rounded-xl border border-line p-3">
                    <div className="flex flex-wrap items-center gap-2"><b>{o.name}</b><Chip tone={o.compatible ? "ok" : "slate"}>{o.blood_group || "?"}{o.compatible ? " · compatible" : ""}</Chip><span className="ml-auto text-xs text-muted">{fmtDate(o.created_at, i18n.language)}</span></div>
                    {o.note && <p className="mt-1 text-sm text-muted">{o.note}</p>}
                    <div className="mt-2 flex flex-wrap items-center gap-2">
                      <a className="btn-soft !min-h-[36px] !px-3 text-sm" href={`tel:${o.phone}`}><Phone className="h-4 w-4" />{o.phone}</a>
                      <select className="input !min-h-[36px] !w-auto !py-0 text-sm" value={o.status} onChange={(e) => offer.mutate({ id: o.id, s: e.target.value })}>{["new", "contacted", "declined", "accepted"].map((s) => <option key={s}>{s}</option>)}</select>
                    </div>
                  </li>
                ))}
              </ul>
            )}
            <p className="mt-3 text-xs text-muted">{t("transplant.offerNote", "Every donor must still be checked by the hospital's transplant team and authorisation committee.")}</p>
          </Card>

          <Card>
            <h2 className="mb-3 font-display text-lg font-bold">{t("transplant.matchesTitle", "Registered donors who match")}</h2>
            {!r.matches.length ? <p className="text-muted">{t("transplant.noMatches", "No registered living-donor pledges match yet.")}</p> : (
              <ul className="space-y-2" data-testid="matches">
                {r.matches.map((m) => (
                  <li key={m.pledge_id} className="flex flex-wrap items-center gap-2 rounded-xl border border-line p-3">
                    <div className="min-w-0 flex-1"><p className="font-semibold">{m.name} <span className="text-muted">· {m.blood_group}{m.city ? " · " + m.city : ""}</span></p><p className="text-xs text-muted">{m.phone}</p></div>
                    {m.can_message && <button className="btn-soft !min-h-[36px] text-sm" onClick={() => contact.mutate(m.pledge_id)}>{t("transplant.askDonor", "Ask gently")}</button>}
                  </li>
                ))}
              </ul>
            )}
          </Card>
        </div>
      </div>

      <div className="mx-auto hidden max-w-xl p-8 text-center print:block">
        <h1 className="text-3xl font-extrabold">Kidney donor needed</h1>
        <p className="mt-4 text-2xl font-bold">{r.patient_name}</p>
        <p className="text-xl">Blood group {r.blood_group}</p>
        <p className="text-lg">{r.hospital_name}{r.city ? ", " + r.city : ""}</p>
        <div className="my-6 flex justify-center"><QR value={url} size={220} /></div>
        <p className="text-lg">Scan to see details or offer to be tested.</p>
        <p className="mt-3 text-sm">Contact: {r.contact_name} {r.contact_phone}</p>
        <p className="mt-6 text-sm">Donation is voluntary and never paid for. The hospital checks every donor.</p>
      </div>
    </>
  );
}
