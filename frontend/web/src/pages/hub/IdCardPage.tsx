import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, Download, FileText, Printer } from "lucide-react";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { useParams } from "react-router-dom";
import { PublicBar } from "@/components/Layout";
import { QR } from "@/components/QR";
import { Card, ErrorState, Field, LoadingBlock, PageHeader, Toasts, useNotify } from "@/components/ui";
import { api, type IdCard } from "@/lib/api";

function CardView({ c, url }: { c: IdCard; url?: string }) {
  const { t } = useTranslation();
  return (
    <div className="card ring-glow overflow-hidden" data-testid="id-card">
      <div className="flex items-center justify-between px-5 py-3 text-white" style={{ backgroundImage: "linear-gradient(135deg,#e11d48,#be123c)" }}>
        <p className="font-display text-lg font-extrabold">{t("transplant.emergencyId", "EMERGENCY: KIDNEY PATIENT")}</p><AlertTriangle className="h-6 w-6" />
      </div>
      <div className="grid gap-4 p-5 sm:grid-cols-[1fr_auto]">
        <div className="space-y-1">
          <p className="font-display text-2xl font-bold">{c.name}{c.age ? `, ${c.age}` : ""}</p>
          <p>{t("transplant.bloodGroup", "Blood group")}: <b className="text-xl">{c.blood_group || "?"}</b> · {t("transplant.stage", "Stage")}: <b>{c.stage ?? "?"}</b>{c.egfr ? ` · eGFR ${c.egfr}` : ""}</p>
          {c.allergies && <p>{t("transplant.allergies", "Allergies")}: <b>{c.allergies}</b></p>}
          <p className="text-sm text-muted">{[c.diabetes && "Diabetes", c.hypertension && "Hypertension"].filter(Boolean).join(" · ")}</p>
          {c.contact_phone && <p className="pt-1">{t("transplant.callFirst", "Call")}: <a className="font-bold underline" href={`tel:${c.contact_phone}`}>{c.contact_name} {c.contact_phone}</a></p>}
        </div>
        {url && <QR value={url} size={120} />}
      </div>
      <ul className="space-y-1 border-t border-[var(--border)] px-5 py-3 text-sm">{c.warnings.map((w) => <li key={w}>⚠ {w}</li>)}</ul>
    </div>
  );
}

export function PublicId() {
  const { token = "" } = useParams();
  const q = useQuery({ queryKey: ["public-id", token], queryFn: () => api.publicIdCard(token), retry: false });
  return (
    <div className="min-h-full"><PublicBar />
      <main className="mx-auto max-w-xl px-4 py-8">{q.isLoading ? <LoadingBlock /> : q.error || !q.data ? <ErrorState error={q.error} /> : <CardView c={q.data} />}</main><Toasts /></div>
  );
}

export default function IdCardPage() {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const notify = useNotify();
  const q = useQuery({ queryKey: ["tx", "idcard"], queryFn: () => api.idCard() });
  const [f, setF] = useState({ blood_group: "", allergies: "", contact_name: "", contact_phone: "", public: true });
  const [ref, setRef] = useState({ to: "", reason: "" });
  useEffect(() => { if (q.data) setF({ blood_group: q.data.blood_group, allergies: q.data.allergies, contact_name: q.data.contact_name, contact_phone: q.data.contact_phone, public: q.data.public }); }, [q.data]);
  const save = useMutation({ mutationFn: () => api.saveIdCard(f), onSuccess: (c) => { qc.setQueryData(["tx", "idcard"], c); notify.ok(t("transplant.cardSaved", "Card saved")); }, onError: (e) => notify.error(e) });
  if (q.isLoading) return <LoadingBlock rows={4} />;
  if (q.error || !q.data) return <ErrorState error={q.error} onRetry={() => void q.refetch()} />;
  const url = `${window.location.origin}/e/${q.data.token}`;
  return (
    <div className="space-y-5">
      <PageHeader title={t("transplant.idTitle", "Emergency ID and exports")} subtitle={t("transplant.idSubtitle", "Paramedics and any hospital can scan the QR to see what matters for a kidney patient.")} />
      <div className="grid gap-5 lg:grid-cols-2">
        <Card>
          <div className="space-y-3">
            <Field label={t("transplant.bloodGroup", "Blood group")}><select className="input" value={f.blood_group} onChange={(e) => setF({ ...f, blood_group: e.target.value })}><option value="">--</option>{["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"].map((g) => <option key={g}>{g}</option>)}</select></Field>
            <Field label={t("transplant.allergies", "Allergies")}><input className="input" value={f.allergies} onChange={(e) => setF({ ...f, allergies: e.target.value })} /></Field>
            <div className="grid gap-3 sm:grid-cols-2"><Field label={t("transplant.contactName", "Contact person")}><input className="input" value={f.contact_name} onChange={(e) => setF({ ...f, contact_name: e.target.value })} /></Field><Field label={t("transplant.contactPhone", "Contact phone")}><input className="input" inputMode="tel" value={f.contact_phone} onChange={(e) => setF({ ...f, contact_phone: e.target.value })} /></Field></div>
            <label className="flex items-center gap-2 text-sm"><input type="checkbox" className="h-5 w-5 accent-[var(--accent)]" checked={f.public} onChange={(e) => setF({ ...f, public: e.target.checked })} />{t("transplant.cardPublic", "Anyone with the QR can open this card")}</label>
            <div className="flex flex-wrap gap-2"><button className="btn-primary" onClick={() => save.mutate()} data-testid="save-card">{t("transplant.saveCard", "Save card")}</button><button className="btn-outline" onClick={() => window.print()}><Printer className="h-4 w-4" />{t("transplant.print", "Print")}</button></div>
          </div>
        </Card>
        <CardView c={q.data} url={url} />
      </div>
      <Card>
        <h2 className="mb-3 font-display text-lg font-bold">{t("transplant.exports", "Records for any hospital")}</h2>
        <div className="grid gap-3 md:grid-cols-2">
          <div><p className="mb-2 text-sm text-muted">{t("transplant.fhirNote", "FHIR file: the standard format hospital systems read (labs with LOINC codes).")}</p><button className="btn-outline" onClick={() => api.exportFhir().catch((e) => notify.error(e))} data-testid="export-fhir"><Download className="h-4 w-4" />{t("transplant.downloadFhir", "Download FHIR (JSON)")}</button></div>
          <div className="space-y-2">
            <input className="input" placeholder={t("transplant.refTo", "Refer to (hospital or doctor)") as string} value={ref.to} onChange={(e) => setRef({ ...ref, to: e.target.value })} />
            <input className="input" placeholder={t("transplant.refReason", "Reason (e.g. transplant evaluation)") as string} value={ref.reason} onChange={(e) => setRef({ ...ref, reason: e.target.value })} />
            <button className="btn-outline" onClick={() => api.openReferral(ref.to, ref.reason).catch((e) => notify.error(e))} data-testid="open-referral"><FileText className="h-4 w-4" />{t("transplant.referral", "Referral letter (PDF)")}</button>
          </div>
        </div>
      </Card>
    </div>
  );
}
