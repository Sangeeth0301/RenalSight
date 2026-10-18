import { useMutation, useQuery } from "@tanstack/react-query";
import { BadgeCheck, HeartHandshake, MessageCircle, ShieldAlert } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useParams } from "react-router-dom";
import { PublicBar } from "@/components/Layout";
import { Card, ErrorState, Field, LoadingBlock, Spinner, Toasts, useNotify } from "@/components/ui";
import { api } from "@/lib/api";
import { waLink } from "@/lib/share";

/** Public, no sign-in. Shows a masked phone number and lets a kind stranger offer to be tested. */
export default function PublicRequest() {
  const { t } = useTranslation();
  const { token = "" } = useParams();
  const notify = useNotify();
  const q = useQuery({ queryKey: ["public-request", token], queryFn: () => api.publicRequest(token), retry: false });
  const [f, setF] = useState({ name: "", blood_group: "", phone: "", note: "", consent: false });
  const [done, setDone] = useState<string | null>(null);
  const send = useMutation({ mutationFn: () => api.publicOffer(token, f), onSuccess: (r) => setDone(r.message), onError: (e) => notify.error(e) });

  return (
    <div className="min-h-full">
      <PublicBar />
      <main className="mx-auto max-w-2xl space-y-5 px-4 py-8">
        {q.isLoading ? <LoadingBlock rows={4} /> : q.error || !q.data ? <ErrorState error={q.error} /> : (
          <>
            <Card className="text-center">
              <HeartHandshake className="mx-auto h-10 w-10 text-accent" />
              <h1 className="mt-2 font-display text-3xl font-extrabold">{t("transplant.pubTitle", "A kidney donor is needed")}</h1>
              <p className="mt-3 text-2xl font-bold" data-testid="pub-patient">{q.data.patient_name}</p>
              <p className="text-lg text-muted">{q.data.hospital_name}{q.data.city ? ", " + q.data.city : ""}</p>
              <div className="mt-4 flex flex-wrap justify-center gap-3">
                <span className="chip bg-accent-soft text-ink !text-base">{t("transplant.bloodGroup", "Blood group")} {q.data.blood_group}</span>
                {q.data.verified && <span className="chip bg-emerald-100 text-emerald-800 !text-base"><BadgeCheck className="h-4 w-4" />{t("transplant.verifiedByDoctor", "Confirmed by a doctor")}</span>}
              </div>
              <p className="mt-3 text-sm text-muted">{t("transplant.canDonate", "Donors with blood group {{g}} can be tested.", { g: q.data.compatible_groups.join(", ") })}</p>
              {q.data.story && <p className="mt-3">{q.data.story}</p>}
              <a className="btn-outline mt-4" target="_blank" rel="noreferrer" href={waLink(`Please help: ${q.data.patient_name} (${q.data.blood_group}) needs a kidney donor. ${window.location.href}`)}><MessageCircle className="h-4 w-4" />{t("transplant.shareThis", "Share this page")}</a>
            </Card>
            <div className="card flex items-start gap-3 border-amber-300/60 p-4"><ShieldAlert className="mt-0.5 h-5 w-5 shrink-0 text-warn" /><p className="text-sm">{q.data.scam_warning}</p></div>
            <Card>
              <h2 className="mb-3 font-display text-xl font-bold">{t("transplant.offerTitle", "I want to be tested")}</h2>
              {done ? <p className="text-lg text-ok" data-testid="offer-done">{done}</p> : (
                <div className="space-y-3">
                  <Field label={t("transplant.yourName", "Your name")}><input className="input" value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} data-testid="offer-name" /></Field>
                  <div className="grid gap-3 sm:grid-cols-2">
                    <Field label={t("transplant.bloodGroup", "Blood group")}><select className="input" value={f.blood_group} onChange={(e) => setF({ ...f, blood_group: e.target.value })}><option value="">{t("transplant.dontKnow", "I don't know")}</option>{["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"].map((g) => <option key={g}>{g}</option>)}</select></Field>
                    <Field label={t("transplant.yourPhone", "Your phone")}><input className="input" inputMode="tel" value={f.phone} onChange={(e) => setF({ ...f, phone: e.target.value })} data-testid="offer-phone" /></Field>
                  </div>
                  <Field label={t("transplant.note", "A short note (optional)")}><textarea className="input min-h-[60px]" maxLength={300} value={f.note} onChange={(e) => setF({ ...f, note: e.target.value })} /></Field>
                  <label className="flex items-start gap-2 text-sm"><input type="checkbox" className="mt-1 h-5 w-5 accent-[var(--accent)]" checked={f.consent} onChange={(e) => setF({ ...f, consent: e.target.checked })} data-testid="offer-consent" />{t("transplant.consentOffer", "I offer this freely. I am not asking for or accepting any payment.")}</label>
                  <button className="btn-primary w-full" disabled={!f.consent || f.name.trim().length < 2 || f.phone.replace(/\D/g, "").length < 7 || send.isPending} onClick={() => send.mutate()} data-testid="offer-send">{send.isPending && <Spinner />}{t("transplant.sendOffer", "Tell the family")}</button>
                </div>
              )}
            </Card>
          </>
        )}
      </main>
      <Toasts />
    </div>
  );
}
