import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";
import { HospitalPicker } from "@/components/HospitalPicker";
import { ShareStudio } from "@/components/ShareStudio";
import { Card, Field, PageHeader, Spinner, useNotify } from "@/components/ui";
import { api, type RequestInput } from "@/lib/api";
import { useSession } from "@/store/session";

const GROUPS = ["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"];
const RELATIONS = ["family", "myself", "father", "mother", "brother", "sister", "son", "daughter", "husband", "wife", "friend"];

export default function RequestNew() {
  const { t } = useTranslation();
  const nav = useNavigate();
  const qc = useQueryClient();
  const notify = useNotify();
  const user = useSession((s) => s.user)!;
  const [f, setF] = useState({ hospital_name: "", hospital_id: null as number | null, patient_name: "", blood_group: "", age: "", city: "", relation: "family", contact_name: user.name, contact_phone: "", urgency: "routine" as "routine" | "soon" | "urgent", story: "" });
  const set = (k: keyof typeof f, v: string | number | null) => setF((p) => ({ ...p, [k]: v }));
  const ready = f.hospital_name.trim().length >= 2 && f.patient_name.trim().length >= 1 && !!f.blood_group && f.contact_phone.replace(/\D/g, "").length >= 7;

  const save = useMutation({
    mutationFn: () => {
      const b: RequestInput = { hospital_name: f.hospital_name, hospital_id: f.hospital_id, patient_name: f.patient_name, blood_group: f.blood_group, age: f.age ? Number(f.age) : null, city: f.city, relation: f.relation, contact_name: f.contact_name, contact_phone: f.contact_phone, urgency: f.urgency, story: f.story };
      return api.createRequest(b);
    },
    onSuccess: (r) => { notify.ok(t("transplant.saved", "Request saved. Your public page is ready.")); void qc.invalidateQueries({ queryKey: ["tx"] }); nav(`/hub/request/${r.id}`); },
    onError: (e) => notify.error(e),
  });

  return (
    <div className="space-y-6">
      <PageHeader title={t("transplant.newTitle", "Ask for a kidney donor")} subtitle={t("transplant.newSubtitle", "Fill in the basics. The message below is written for you and updates as you type.")} />
      <Card>
        <div className="grid gap-4 md:grid-cols-2">
          <Field label={t("transplant.hospital", "Hospital")} hint={t("transplant.hospitalHint", "Start typing: AIIMS, KMCH, a Kolkata hospital... or write any name.")}>
            <HospitalPicker value={f.hospital_name} onChange={(v) => { set("hospital_name", v); set("hospital_id", null); }} onPick={(h) => { set("hospital_id", h.id); if (!f.city) set("city", h.city); }} />
          </Field>
          <Field label={t("transplant.city", "City")}><input className="input" value={f.city} onChange={(e) => set("city", e.target.value)} data-testid="city" /></Field>
          <Field label={t("transplant.patientName", "Patient name")}><input className="input" value={f.patient_name} onChange={(e) => set("patient_name", e.target.value)} data-testid="patient-name" /></Field>
          <div className="grid grid-cols-2 gap-3">
            <Field label={t("transplant.bloodGroup", "Blood group")}>
              <select className="input" value={f.blood_group} onChange={(e) => set("blood_group", e.target.value)} data-testid="blood-group"><option value="">--</option>{GROUPS.map((g) => <option key={g}>{g}</option>)}</select>
            </Field>
            <Field label={t("transplant.age", "Age")}><input className="input" inputMode="numeric" value={f.age} onChange={(e) => set("age", e.target.value.replace(/\D/g, "").slice(0, 3))} /></Field>
          </div>
          <Field label={t("transplant.relation", "Who is the patient to you?")}>
            <select className="input" value={f.relation} onChange={(e) => set("relation", e.target.value)}>{RELATIONS.map((r) => <option key={r} value={r}>{r}</option>)}</select>
          </Field>
          <Field label={t("transplant.urgency", "How urgent?")}>
            <select className="input" value={f.urgency} onChange={(e) => set("urgency", e.target.value)}><option value="routine">{t("transplant.routine", "Planned")}</option><option value="soon">{t("transplant.soon", "Within weeks")}</option><option value="urgent">{t("transplant.urgent", "Urgent")}</option></select>
          </Field>
          <Field label={t("transplant.contactName", "Contact person")}><input className="input" value={f.contact_name} onChange={(e) => set("contact_name", e.target.value)} /></Field>
          <Field label={t("transplant.contactPhone", "Contact phone / WhatsApp")}><input className="input" inputMode="tel" placeholder="+91 98xxxxxxxx" value={f.contact_phone} onChange={(e) => set("contact_phone", e.target.value)} data-testid="contact-phone" /></Field>
        </div>
        <div className="mt-4"><Field label={t("transplant.story", "Anything you want to add (optional)")}><textarea className="input min-h-[70px]" maxLength={300} value={f.story} onChange={(e) => set("story", e.target.value)} /></Field></div>
      </Card>

      <Card>
        <h2 className="mb-4 font-display text-lg font-bold">{t("transplant.preview", "Your message")}</h2>
        {!ready ? <p className="text-muted">{t("transplant.fillFirst", "Add hospital, patient name, blood group and phone to see the message.")}</p> : (
          <ShareStudio ready={ready} input={{ hospital: f.hospital_name, patient_name: f.patient_name, blood_group: f.blood_group, contact_name: f.contact_name, contact_phone: f.contact_phone, city: f.city, age: f.age ? Number(f.age) : null, relation: f.relation, tone: f.urgency === "urgent" ? "urgent" : "warm", extra: f.story }} />
        )}
      </Card>

      <div className="flex justify-end">
        <button className="btn-primary" disabled={!ready || save.isPending} onClick={() => save.mutate()} data-testid="save-request">{save.isPending && <Spinner />}{t("transplant.saveRequest", "Save and create public page")}</button>
      </div>
    </div>
  );
}
