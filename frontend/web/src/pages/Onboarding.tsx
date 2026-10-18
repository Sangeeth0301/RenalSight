import { Check, Copy } from "lucide-react";
import { useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";
import { Card, Field, Progress, Spinner, useNotify, Toasts } from "@/components/ui";
import { api, ApiError, type Lang, type Sex } from "@/lib/api";
import { homeFor } from "@/lib/hooks";
import { LANGS, setLanguage } from "@/i18n";
import { useSession } from "@/store/session";
import { PublicBar } from "@/components/Layout";

export default function Onboarding() {
  const { t } = useTranslation();
  const nav = useNavigate();
  const user = useSession((s) => s.user)!;
  const setUser = useSession((s) => s.setUser);
  const notify = useNotify();
  const isDoctor = user.role === "doctor";
  const needsHealth = user.role === "patient" || user.role === "caregiver";
  const steps = isDoctor ? ["profile", "done"] : user.role === "patient" ? ["profile", "doctor", "done"] : ["profile", "done"];
  const [step, setStep] = useState(0);
  const [busy, setBusy] = useState(false);
  const [birthYear, setBirthYear] = useState<string>(user.birth_year ? String(user.birth_year) : "");
  const [sex, setSex] = useState<Sex | "">(user.sex ?? "");
  const [diabetes, setDiabetes] = useState(user.diabetes);
  const [hypertension, setHypertension] = useState(user.hypertension);
  const [lang, setLang] = useState<Lang>(user.language);
  const [code, setCode] = useState("");
  const [linked, setLinked] = useState<string | null>(null);
  const [codeErr, setCodeErr] = useState("");
  const [copied, setCopied] = useState(false);
  const current = steps[step];
  const thisYear = new Date().getFullYear();

  const saveProfile = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    try {
      const body: Parameters<typeof api.updateProfile>[0] = { language: lang };
      if (needsHealth) {
        body.birth_year = Number(birthYear);
        if (sex) body.sex = sex;
        body.diabetes = diabetes;
        body.hypertension = hypertension;
      }
      const u = await api.updateProfile(body);
      setUser(u);
      if (lang !== user.language) await setLanguage(lang);
      setStep(step + 1);
    } catch (e2) { notify.error(e2); } finally { setBusy(false); }
  };

  const link = async () => {
    setBusy(true); setCodeErr("");
    try {
      const r = await api.linkDoctor(code.trim().toUpperCase());
      setLinked(r.doctor.name);
      setUser(await api.me());
    } catch (e) {
      if (e instanceof ApiError && e.status === 404) setCodeErr(t("onboarding.notFound")); else notify.error(e);
    } finally { setBusy(false); }
  };

  return (
    <div className="min-h-full bg-bg">
      <PublicBar />
      <main className="mx-auto max-w-lg px-4 py-10">
        <Progress value={step + 1} max={steps.length} className="mb-5" />
        {current === "profile" && (
          <Card>
            <h1 className="text-2xl font-bold">{t("onboarding.title")}</h1>
            {needsHealth && <p className="mb-4 text-muted">{t("onboarding.why")}</p>}
            <form onSubmit={saveProfile} className="space-y-4">
              {needsHealth && (
                <>
                  <Field label={t("onboarding.birthYear")} htmlFor="by">
                    <input id="by" data-testid="birth-year" type="number" min={1900} max={thisYear} required className="input" value={birthYear} onChange={(e) => setBirthYear(e.target.value)} />
                  </Field>
                  <Field label={t("onboarding.sex")}>
                    <div className="grid grid-cols-2 gap-3">
                      {(["male", "female"] as const).map((s) => (
                        <button type="button" key={s} data-testid={`sex-${s}`} onClick={() => setSex(s)} className={`min-h-[48px] rounded-xl2 border-2 font-semibold ${sex === s ? "border-accent bg-accent-soft" : "border-line bg-white"}`}>{t(`onboarding.${s}`)}</button>
                      ))}
                    </div>
                  </Field>
                  <label className="flex min-h-[44px] items-center gap-3"><input type="checkbox" className="h-5 w-5 accent-[var(--accent)]" checked={diabetes} onChange={(e) => setDiabetes(e.target.checked)} data-testid="diabetes" />{t("onboarding.diabetes")}</label>
                  <label className="flex min-h-[44px] items-center gap-3"><input type="checkbox" className="h-5 w-5 accent-[var(--accent)]" checked={hypertension} onChange={(e) => setHypertension(e.target.checked)} data-testid="hypertension" />{t("onboarding.hypertension")}</label>
                </>
              )}
              <Field label={t("onboarding.language")} htmlFor="l">
                <select id="l" className="input" value={lang} onChange={(e) => setLang(e.target.value as Lang)}>{LANGS.map((l) => <option key={l} value={l}>{t(`lang.${l}`)}</option>)}</select>
              </Field>
              <button className="btn-primary w-full" disabled={busy || (needsHealth && (!sex || !birthYear))} data-testid="save-profile">{busy ? <Spinner className="text-white" /> : t("app.next")}</button>
            </form>
          </Card>
        )}
        {current === "doctor" && (
          <Card>
            <h1 className="text-2xl font-bold">{t("onboarding.doctorTitle")}</h1>
            <p className="mb-4 text-muted">{t("onboarding.doctorHelp")}</p>
            {linked ? (
              <p className="flex items-center gap-2 rounded-xl bg-emerald-50 p-3 font-semibold text-emerald-800"><Check className="h-5 w-5" />{t("onboarding.linked", { name: linked })}</p>
            ) : (
              <div className="space-y-3">
                <Field label={t("onboarding.doctorCode")} error={codeErr}><input data-testid="doctor-code" className="input uppercase tracking-[0.3em]" maxLength={8} value={code} onChange={(e) => setCode(e.target.value)} /></Field>
                <button className="btn-primary w-full" disabled={busy || code.trim().length < 6} onClick={link} data-testid="link-doctor">{t("onboarding.linkDoctor")}</button>
              </div>
            )}
            <div className="mt-4 flex gap-3">
              <button className="btn-ghost flex-1" onClick={() => setStep(step + 1)}>{linked ? t("app.next") : t("onboarding.skip")}</button>
            </div>
          </Card>
        )}
        {current === "done" && (
          <Card className="text-center">
            <div className="mx-auto mb-3 grid h-16 w-16 place-items-center rounded-full bg-emerald-100 text-emerald-700"><Check className="h-8 w-8" /></div>
            <h1 className="text-2xl font-bold">{t("auth.welcome", { name: user.name })}</h1>
            {isDoctor && user.doctor_code && (
              <div className="mt-5 rounded-xl2 border border-line bg-accent-soft p-4">
                <p className="text-sm font-medium">{t("onboarding.yourDoctorCode")}</p>
                <p className="my-2 select-all text-4xl font-extrabold tracking-[0.35em]" data-testid="my-doctor-code">{user.doctor_code}</p>
                <button className="btn-outline" onClick={() => { void navigator.clipboard?.writeText(user.doctor_code!); setCopied(true); setTimeout(() => setCopied(false), 1500); }}>
                  {copied ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}{copied ? t("app.yes") : t("app.save")}
                </button>
              </div>
            )}
            <button className="btn-primary mt-6 w-full" data-testid="finish" onClick={() => nav(homeFor(user.role))}>{t("onboarding.done")}</button>
          </Card>
        )}
      </main>
      <Toasts />
    </div>
  );
}
