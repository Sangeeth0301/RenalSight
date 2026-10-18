import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CalendarCheck, FlaskConical, MapPin, Phone, Pill, Stethoscope, Activity } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import { Card, Chip, DemoBadge, Disclaimer, EmptyState, ErrorState, Field, LoadingBlock, Modal, PageHeader, Spinner, useNotify } from "@/components/ui";
import { api, type Provider, type ProviderKind } from "@/lib/api";
import { fmtTime } from "@/lib/utils";
import { useSession } from "@/store/session";

const ICON = { nephrologist: Stethoscope, dialysis: Activity, lab: FlaskConical, pharmacy: Pill } as const;
const REGIONS = [["all", "All"], ["IN-TN", "Tamil Nadu"], ["IN-WB", "West Bengal"], ["IN-AP", "Andhra Pradesh"], ["IN-TG", "Telangana"], ["IN-KA", "Karnataka"]] as const;

export default function CareHub() {
  const { t, i18n } = useTranslation();
  const qc = useQueryClient();
  const notify = useNotify();
  const user = useSession((s) => s.user)!;
  const [kind, setKind] = useState<"all" | ProviderKind>("all");
  const [region, setRegion] = useState("all");
  const [book, setBook] = useState<{ provider: Provider | null } | null>(null);
  const [when, setWhen] = useState("");
  const [note, setNote] = useState("");

  const overview = useQuery({ queryKey: ["care-hub", "overview"], queryFn: () => api.careOverview() });
  const providers = useQuery({ queryKey: ["care-hub", "providers", kind, region], queryFn: () => api.careProviders({ kind: kind === "all" ? undefined : kind, region }) });
  const appts = useQuery({ queryKey: ["care-hub", "appointments"], queryFn: () => api.appointments() });

  const create = useMutation({
    mutationFn: () => api.bookAppointment({ provider_id: book?.provider?.id, with_my_doctor: !book?.provider, starts_at: new Date(when).toISOString(), note }),
    onSuccess: () => { notify.ok(t("hub.booked")); setBook(null); setWhen(""); setNote(""); void qc.invalidateQueries({ queryKey: ["care-hub"] }); },
    onError: (e) => notify.error(e),
  });
  const cancel = useMutation({ mutationFn: (id: number) => api.setAppointmentStatus(id, "cancelled"), onSuccess: () => void qc.invalidateQueries({ queryKey: ["care-hub"] }), onError: (e) => notify.error(e) });

  const o = overview.data;
  const stats: [string, number | string | undefined, typeof Stethoscope][] = [
    [t("hub.matched"), o?.specialists_matched, Stethoscope], [t("hub.upcoming"), o?.appointments_upcoming, CalendarCheck],
    [t("hub.pending"), o?.prescriptions_pending, Pill], [t("hub.adherence"), o ? `${Math.round(o.adherence_7d * 100)}%` : undefined, Activity],
  ];
  const minWhen = new Date(Date.now() + 3600_000).toISOString().slice(0, 16);

  return (
    <>
      <PageHeader title={t("hub.title")} subtitle={t("hub.subtitle")} chip={<DemoBadge />}
        right={user.doctor_id ? <button className="btn-primary" onClick={() => setBook({ provider: null })} data-testid="book-doctor"><CalendarCheck className="h-4 w-4" />{t("hub.bookDoctor")}</button> : <Link to="/settings" className="btn-outline">{t("hub.needDoctor")}</Link>} />
      <div className="mb-5 grid grid-cols-2 gap-3 lg:grid-cols-4" data-testid="hub-stats">
        {stats.map(([label, v, Icon]) => <Card key={label} className="flex items-center gap-3 !p-4"><span className="grid h-11 w-11 place-items-center rounded-xl bg-accent-soft text-accent"><Icon className="h-5 w-5" /></span><div><p className="text-xs text-muted">{label}</p><p className="text-2xl font-extrabold">{v ?? "-"}</p></div></Card>)}
      </div>
      <p className="mb-4 rounded-xl bg-amber-50 p-3 text-sm text-amber-900" data-testid="demo-note">{t("hub.demoNote")}</p>
      <div className="mb-4 flex flex-wrap items-center gap-2">
        {(["all", "nephrologist", "dialysis", "lab", "pharmacy"] as const).map((k) => <button key={k} onClick={() => setKind(k)} data-testid={`kind-${k}`} className={`chip !px-3 !py-2 text-sm ${kind === k ? "bg-accent text-white" : "bg-slate-100 hover:bg-accent-soft"}`}>{t(`hub.kinds.${k}`)}</button>)}
        <select className="input !w-auto" value={region} onChange={(e) => setRegion(e.target.value)} aria-label={t("hub.region")}>{REGIONS.map(([c, n]) => <option key={c} value={c}>{n}</option>)}</select>
      </div>

      {providers.isLoading ? <LoadingBlock /> : providers.error ? <ErrorState error={providers.error} onRetry={() => providers.refetch()} /> : (providers.data?.providers ?? []).length === 0 ? <EmptyState title={t("research.none")} /> : (
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3" data-testid="providers">
          {providers.data!.providers.map((p) => {
            const Icon = ICON[p.kind];
            return (
              <Card key={p.id} className="flex flex-col gap-2" data-testid="provider">
                <div className="flex items-start gap-3"><span className="grid h-11 w-11 shrink-0 place-items-center rounded-xl bg-accent-soft text-accent"><Icon className="h-5 w-5" /></span>
                  <div className="min-w-0 flex-1"><p className="font-bold leading-tight">{p.name}</p><p className="flex items-center gap-1 text-sm text-muted"><MapPin className="h-3.5 w-3.5" />{p.city}</p></div>
                  {(p.fit ?? 0) >= 1 && <Chip tone="ok">{t("hub.fit")}</Chip>}</div>
                <p className="text-sm">{p.services}</p>
                <p className="text-xs text-muted">{t("hub.languages")}: {p.languages.map((l) => t(`lang.${l}`)).join(", ")}</p>
                <p className="flex items-center gap-1 text-xs text-muted"><Phone className="h-3.5 w-3.5" />{p.phone || t("hub.noPhone")}</p>
                <div className="mt-auto flex items-center justify-between pt-1">{p.is_demo ? <DemoBadge /> : <span />}<button className="btn-soft !min-h-[40px]" onClick={() => setBook({ provider: p })} data-testid="book">{t("hub.book")}</button></div>
              </Card>
            );
          })}
        </div>
      )}

      <h2 className="mb-3 mt-8 text-lg font-bold">{t("hub.mine")}</h2>
      {(appts.data ?? []).length === 0 ? <p className="text-muted">{t("hub.none")}</p> : (
        <div className="space-y-2" data-testid="appointments">
          {appts.data!.map((a) => (
            <Card key={a.id} className="flex flex-wrap items-center justify-between gap-3 !p-4" data-testid="appointment">
              <div><p className="font-semibold">{a.doctor ? `Dr. ${a.doctor.name}` : a.provider?.name}</p><p className="text-sm text-muted">{fmtTime(a.starts_at, i18n.language)}{a.note ? ` · ${a.note}` : ""}</p></div>
              <div className="flex items-center gap-2"><Chip tone={a.status === "confirmed" ? "ok" : a.status === "cancelled" ? "slate" : "warn"}>{t(`hub.status.${a.status}`)}</Chip>
                {a.status !== "cancelled" && <button className="btn-outline !min-h-[36px] text-sm" onClick={() => cancel.mutate(a.id)}>{t("hub.cancel")}</button>}</div>
            </Card>
          ))}
        </div>
      )}

      <Modal open={!!book} onClose={() => setBook(null)} title={book?.provider ? book.provider.name : t("hub.bookDoctor")}>
        <div className="space-y-3">
          <Field label={t("hub.when")}><input data-testid="when" type="datetime-local" min={minWhen} className="input" value={when} onChange={(e) => setWhen(e.target.value)} /></Field>
          <Field label={t("hub.note")}><input className="input" maxLength={300} value={note} onChange={(e) => setNote(e.target.value)} /></Field>
          <div className="flex justify-end gap-2"><button className="btn-outline" onClick={() => setBook(null)}>{t("app.cancel")}</button>
            <button className="btn-primary" disabled={!when || new Date(when) <= new Date() || create.isPending} onClick={() => create.mutate()} data-testid="confirm-book">{create.isPending ? <Spinner className="text-white" /> : t("hub.book")}</button></div>
        </div>
      </Modal>
      <Disclaimer />
    </>
  );
}
