import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Heart } from "lucide-react";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { QR } from "@/components/QR";
import { Card, Field, LoadingBlock, PageHeader, Segmented, Spinner, useNotify } from "@/components/ui";
import { api, type PledgeInput } from "@/lib/api";
import { cn } from "@/lib/utils";
import { useSession } from "@/store/session";

const GROUPS = ["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"];

export default function Donate() {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const notify = useNotify();
  const user = useSession((s) => s.user)!;
  const meta = useQuery({ queryKey: ["tx", "meta"], queryFn: () => api.txMeta() });
  const mine = useQuery({ queryKey: ["tx", "pledge"], queryFn: () => api.myPledge() });
  const [f, setF] = useState<PledgeInput>({ name: user.name, blood_group: "", city: "", phone: "", kind: "deceased", organs: ["kidney", "heart", "cornea"], family_informed: false, consent: false });
  useEffect(() => { if (mine.data) setF({ name: mine.data.name, blood_group: mine.data.blood_group, city: mine.data.city, phone: mine.data.phone, kind: mine.data.kind, organs: mine.data.organs, family_informed: mine.data.family_informed, consent: true }); }, [mine.data]);

  const allowed = f.kind === "living" ? meta.data?.organs_living ?? ["kidney", "liver"] : meta.data?.organs_deceased ?? ["kidney", "heart", "liver", "lungs", "pancreas", "cornea", "skin", "bone"];
  const organs = f.organs.filter((o) => allowed.includes(o));
  const toggle = (o: string) => setF((p) => ({ ...p, organs: p.organs.includes(o) ? p.organs.filter((x) => x !== o) : [...p.organs, o] }));
  const save = useMutation({ mutationFn: () => api.pledge({ ...f, organs }), onSuccess: (r) => { notify.ok(r.note ?? "Saved"); void qc.invalidateQueries({ queryKey: ["tx"] }); }, onError: (e) => notify.error(e) });
  const withdraw = useMutation({ mutationFn: () => api.withdrawPledge(), onSuccess: () => { notify.info(t("transplant.withdrawn", "Your pledge was withdrawn.")); setF((p) => ({ ...p, consent: false })); void qc.invalidateQueries({ queryKey: ["tx"] }); }, onError: (e) => notify.error(e) });

  if (mine.isLoading) return <LoadingBlock rows={4} />;
  return (
    <div className="space-y-6">
      <PageHeader title={t("transplant.donateTitle", "Pledge to donate")} subtitle={t("transplant.donateSubtitle", "One decision can save several lives. It is free, voluntary and you can withdraw it any time.")} />
      <div className="grid gap-6 lg:grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)]">
        <Card>
          <div className="space-y-4">
            <div>
              <p className="label">{t("transplant.kindTitle", "What do you want to pledge?")}</p>
              <Segmented value={f.kind} onChange={(kind) => setF({ ...f, kind })} options={[{ value: "deceased", label: t("transplant.afterDeath", "After death") }, { value: "living", label: t("transplant.whileAlive", "While alive") }, { value: "both", label: t("transplant.both", "Both") }]} />
              <p className="mt-2 text-xs text-muted">{f.kind === "living" ? t("transplant.livingNote", "A living person can donate one kidney or part of the liver. Hearts and other organs are only donated after death.") : t("transplant.deceasedNote", "After brain-stem or circulatory death, doctors may retrieve a heart, kidneys, liver, lungs, pancreas, eyes and tissues. Your family is asked at that time, so tell them now.")}</p>
            </div>
            <div>
              <p className="label">{t("transplant.organs", "Organs and tissues")}</p>
              <div className="flex flex-wrap gap-2" data-testid="organs">
                {allowed.map((o) => (
                  <button key={o} type="button" onClick={() => toggle(o)} aria-pressed={organs.includes(o)} className={cn("min-h-[40px] rounded-xl border px-3 font-semibold capitalize transition", organs.includes(o) ? "border-transparent text-[color:var(--on-accent)]" : "border-line")}
                    style={organs.includes(o) ? { backgroundImage: "linear-gradient(135deg,var(--accent),var(--accent-2))" } : undefined}>{o === "heart" ? "❤ heart" : o}</button>
                ))}
              </div>
            </div>
            <div className="grid gap-3 sm:grid-cols-2">
              <Field label={t("transplant.fullName", "Full name")}><input className="input" value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} /></Field>
              <Field label={t("transplant.bloodGroup", "Blood group")}><select className="input" value={f.blood_group} onChange={(e) => setF({ ...f, blood_group: e.target.value })} data-testid="pledge-bg"><option value="">--</option>{GROUPS.map((g) => <option key={g}>{g}</option>)}</select></Field>
              <Field label={t("transplant.city", "City")}><input className="input" value={f.city} onChange={(e) => setF({ ...f, city: e.target.value })} /></Field>
              <Field label={t("transplant.yourPhone", "Your phone")} hint={t("transplant.phoneHint", "Only coordinators see it in full.")}><input className="input" inputMode="tel" value={f.phone} onChange={(e) => setF({ ...f, phone: e.target.value })} /></Field>
            </div>
            <label className="flex items-start gap-2 text-sm"><input type="checkbox" className="mt-1 h-5 w-5 accent-[var(--accent)]" checked={!!f.family_informed} onChange={(e) => setF({ ...f, family_informed: e.target.checked })} />{t("transplant.familyInformed", "I have told my family about my wish.")}</label>
            <label className="flex items-start gap-2 text-sm"><input type="checkbox" className="mt-1 h-5 w-5 accent-[var(--accent)]" checked={f.consent} onChange={(e) => setF({ ...f, consent: e.target.checked })} data-testid="pledge-consent" />{t("transplant.consentPledge", "I choose this freely. I understand I will not be paid and that I can withdraw at any time.")}</label>
            <div className="flex flex-wrap gap-2">
              <button className="btn-primary" disabled={!f.consent || !f.blood_group || organs.length === 0 || f.name.trim().length < 2 || save.isPending} onClick={() => save.mutate()} data-testid="pledge-save">{save.isPending ? <Spinner /> : <Heart className="h-4 w-4" />}{mine.data ? t("transplant.updatePledge", "Update pledge") : t("transplant.savePledge", "Save my pledge")}</button>
              {mine.data && <button className="btn-outline" onClick={() => withdraw.mutate()}>{t("transplant.withdraw", "Withdraw my pledge")}</button>}
            </div>
          </div>
        </Card>

        <div className="space-y-4">
          <div className="card ring-glow p-5 text-center" data-testid="donor-card">
            <p className="text-xs font-bold uppercase tracking-widest text-muted">{t("transplant.donorCard", "Donor card")}</p>
            <Heart className="mx-auto my-2 h-10 w-10 text-danger" fill="currentColor" />
            <p className="font-display text-xl font-bold">{mine.data?.name ?? f.name}</p>
            <p className="text-lg font-bold text-gradient">{mine.data?.blood_group || f.blood_group || "--"}</p>
            <p className="mt-1 text-sm capitalize text-muted">{(mine.data?.organs ?? organs).join(", ") || "-"}</p>
            {mine.data && <div className="mt-3 flex justify-center"><QR value={`RenalSight donor pledge: ${mine.data.name} ${mine.data.blood_group} (${mine.data.kind}: ${mine.data.organs.join(", ")})`} size={120} /></div>}
          </div>
          <Card><p className="text-sm text-muted">{meta.data?.safety[1]}</p><p className="mt-2 text-sm text-muted">{meta.data?.safety[2]}</p></Card>
        </div>
      </div>
    </div>
  );
}
