import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";
import { Card, Field, PageHeader, Spinner, useNotify } from "@/components/ui";
import { api, ApiError, type Lang, type Sex } from "@/lib/api";
import { LANGS, setLanguage } from "@/i18n";
import { useSession } from "@/store/session";

export default function Settings() {
  const { t, i18n } = useTranslation();
  const nav = useNavigate();
  const qc = useQueryClient();
  const notify = useNotify();
  const s = useSession();
  const user = s.user!;
  const health = user.role === "patient" || user.role === "caregiver";
  const [name, setName] = useState(user.name);
  const [birthYear, setBirthYear] = useState(user.birth_year ? String(user.birth_year) : "");
  const [sex, setSex] = useState<Sex | "">(user.sex ?? "");
  const [diabetes, setDiabetes] = useState(user.diabetes);
  const [hypertension, setHypertension] = useState(user.hypertension);
  const [code, setCode] = useState("");
  const [codeErr, setCodeErr] = useState("");

  const save = useMutation({
    mutationFn: () => api.updateProfile({ name, ...(health ? { birth_year: birthYear ? Number(birthYear) : undefined, sex: sex || undefined, diabetes, hypertension } : {}) }),
    onSuccess: (u) => { s.setUser(u); void qc.invalidateQueries(); notify.ok(t("labs.saved")); },
    onError: (e) => notify.error(e),
  });
  const link = useMutation({
    mutationFn: () => api.linkDoctor(code.trim().toUpperCase()),
    onSuccess: async (r) => { s.setUser(await api.me()); setCode(""); notify.ok(t("onboarding.linked", { name: r.doctor.name })); },
    onError: (e) => (e instanceof ApiError && e.status === 404 ? setCodeErr(t("onboarding.notFound")) : notify.error(e)),
  });
  const unlink = useMutation({ mutationFn: () => api.unlinkDoctor(), onSuccess: async () => { s.setUser(await api.me()); }, onError: (e) => notify.error(e) });
  const clear = useMutation({ mutationFn: () => api.clearBuddyHistory(), onSuccess: () => notify.ok(t("buddy.clear")), onError: (e) => notify.error(e) });

  return (
    <>
      <PageHeader title={t("nav.settings")} />
      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <form onSubmit={(e: FormEvent) => { e.preventDefault(); save.mutate(); }} className="space-y-3">
            <Field label={t("auth.name")}><input className="input" value={name} onChange={(e) => setName(e.target.value)} required /></Field>
            <p className="text-sm text-muted">{user.email} · {t(`roles.${user.role}`)}</p>
            {health && <>
              <Field label={t("onboarding.birthYear")}><input data-testid="s-birth" type="number" className="input" value={birthYear} onChange={(e) => setBirthYear(e.target.value)} /></Field>
              <Field label={t("onboarding.sex")}><div className="grid grid-cols-2 gap-3">{(["male", "female"] as const).map((x) => <button type="button" key={x} onClick={() => setSex(x)} className={`min-h-[44px] rounded-xl2 border-2 font-semibold ${sex === x ? "border-accent bg-accent-soft" : "border-line bg-white"}`}>{t(`onboarding.${x}`)}</button>)}</div></Field>
              <label className="flex min-h-[44px] items-center gap-3"><input type="checkbox" className="h-5 w-5 accent-[var(--accent)]" checked={diabetes} onChange={(e) => setDiabetes(e.target.checked)} />{t("onboarding.diabetes")}</label>
              <label className="flex min-h-[44px] items-center gap-3"><input type="checkbox" className="h-5 w-5 accent-[var(--accent)]" checked={hypertension} onChange={(e) => setHypertension(e.target.checked)} />{t("onboarding.hypertension")}</label>
            </>}
            <button className="btn-primary w-full" disabled={save.isPending} data-testid="s-save">{save.isPending ? <Spinner className="text-white" /> : t("app.save")}</button>
          </form>
        </Card>
        <div className="space-y-6">
          <Card>
            <h2 className="mb-3 text-lg font-bold">{t("lang.change")}</h2>
            <div className="grid grid-cols-2 gap-2">{LANGS.map((l: Lang) => <button key={l} className={`min-h-[48px] rounded-xl2 border-2 font-semibold ${i18n.language === l ? "border-accent bg-accent-soft" : "border-line"}`} onClick={() => void setLanguage(l)}>{t(`lang.${l}`)}</button>)}</div>
            <h2 className="mb-2 mt-5 text-lg font-bold">Accessibility</h2>
            <label className="flex min-h-[44px] items-center gap-3"><input type="checkbox" className="h-5 w-5 accent-[var(--accent)]" checked={s.largeText} onChange={s.toggleLargeText} />{t("a11y.largeText")}</label>
            <label className="flex min-h-[44px] items-center gap-3"><input type="checkbox" className="h-5 w-5 accent-[var(--accent)]" checked={s.highContrast} onChange={s.toggleHighContrast} />{t("a11y.highContrast")}</label>
          </Card>
          {user.role === "patient" && (
            <Card>
              <h2 className="mb-2 text-lg font-bold">{t("onboarding.doctorTitle")}</h2>
              {user.doctor_id ? (
                <div className="flex items-center justify-between gap-3"><p className="font-medium">✔ #{user.doctor_id}</p><button className="btn-outline" onClick={() => unlink.mutate()}>{t("app.delete")}</button></div>
              ) : (
                <div className="space-y-3"><p className="text-sm text-muted">{t("onboarding.doctorHelp")}</p>
                  <Field label={t("onboarding.doctorCode")} error={codeErr}><input data-testid="s-code" className="input uppercase tracking-[0.3em]" maxLength={8} value={code} onChange={(e) => { setCode(e.target.value); setCodeErr(""); }} /></Field>
                  <button className="btn-primary w-full" disabled={code.trim().length < 6 || link.isPending} onClick={() => link.mutate()} data-testid="s-link">{t("onboarding.linkDoctor")}</button></div>
              )}
            </Card>
          )}
          {user.role === "doctor" && user.doctor_code && <Card><p className="text-sm text-muted">{t("doctor.yourCode")}</p><p className="text-4xl font-extrabold tracking-[0.3em]">{user.doctor_code}</p></Card>}
          {health && <button className="btn-outline w-full" onClick={() => clear.mutate()}>{t("buddy.clear")}</button>}
          <button className="btn-ghost w-full text-danger" onClick={() => { s.logout(); qc.clear(); nav("/"); }}>{t("nav.logout")}</button>
        </div>
      </div>
    </>
  );
}
