import { useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { PublicBar } from "@/components/Layout";
import { Card, Field, Segmented, Spinner, Toasts, useNotify } from "@/components/ui";
import { api, ApiError, auth, type AuthResult, type Lang, type Role } from "@/lib/api";
import { homeFor } from "@/lib/hooks";
import { currentLang, LANGS } from "@/i18n";
import { useSession } from "@/store/session";

function afterAuth(res: AuthResult, setUser: (u: any) => void, nav: (to: string) => void, register: boolean) {
  auth.set(res.access_token);
  setUser(res.user);
  const u = res.user;
  const needsProfile = (u.role === "patient" || u.role === "caregiver") && (u.birth_year === null || u.sex === null);
  nav(register || needsProfile ? "/onboarding" : homeFor(u.role));
}

export function Login() {
  const { t } = useTranslation();
  const nav = useNavigate();
  const setUser = useSession((s) => s.setUser);
  const notify = useNotify();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true); setErr("");
    try {
      afterAuth(await api.login({ email, password }), setUser, nav, false);
    } catch (e2) {
      if (e2 instanceof ApiError && e2.status === 401) setErr(t("auth.errors.wrong"));
      else notify.error(e2);
    } finally { setBusy(false); }
  };

  return (
    <div className="min-h-full bg-bg">
      <PublicBar />
      <main className="mx-auto grid max-w-md px-4 py-12">
        <Card>
          <h1 className="mb-4 text-2xl font-bold">{t("auth.signIn")}</h1>
          <form onSubmit={submit} className="space-y-4">
            <Field label={t("auth.email")} htmlFor="email"><input id="email" data-testid="email" type="email" required autoComplete="email" className="input" value={email} onChange={(e) => setEmail(e.target.value)} /></Field>
            <Field label={t("auth.password")} htmlFor="password" error={err}><input id="password" data-testid="password" type="password" required autoComplete="current-password" className="input" value={password} onChange={(e) => setPassword(e.target.value)} /></Field>
            <button className="btn-primary w-full" disabled={busy} data-testid="submit">{busy ? <Spinner className="text-white" /> : t("auth.signIn")}</button>
          </form>
          <p className="mt-4 text-center text-sm text-muted">{t("auth.noAccount")} <Link to="/register" className="font-semibold text-accent">{t("auth.register")}</Link></p>
        </Card>
      </main>
      <Toasts />
    </div>
  );
}

export function Register() {
  const { t } = useTranslation();
  const nav = useNavigate();
  const [sp] = useSearchParams();
  const setUser = useSession((s) => s.setUser);
  const notify = useNotify();
  const initialRole = (["patient", "caregiver", "doctor"].includes(sp.get("role") ?? "") ? sp.get("role") : "patient") as Exclude<Role, "admin">;
  const [role, setRole] = useState<Exclude<Role, "admin">>(initialRole);
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [language, setLang] = useState<Lang>(currentLang());
  const [busy, setBusy] = useState(false);
  const [errs, setErrs] = useState<{ email?: string; password?: string }>({});

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (password.length < 8) { setErrs({ password: t("auth.errors.weak") }); return; }
    setBusy(true); setErrs({});
    try {
      afterAuth(await api.register({ email, password, name, role, language }), setUser, nav, true);
    } catch (e2) {
      if (e2 instanceof ApiError && e2.status === 409) setErrs({ email: t("auth.errors.exists") });
      else if (e2 instanceof ApiError && e2.status === 422) setErrs({ email: t("auth.errors.email") });
      else notify.error(e2);
    } finally { setBusy(false); }
  };

  return (
    <div className="min-h-full bg-bg">
      <PublicBar />
      <main className="mx-auto grid max-w-md px-4 py-10">
        <Card>
          <h1 className="mb-4 text-2xl font-bold">{t("auth.register")}</h1>
          <form onSubmit={submit} className="space-y-4">
            <Field label={t("auth.role")}>
              <Segmented value={role} onChange={setRole} options={(["patient", "caregiver", "doctor"] as const).map((r) => ({ value: r, label: t(`roles.${r}`) }))} />
            </Field>
            <Field label={t("auth.name")} htmlFor="name"><input id="name" data-testid="name" required className="input" value={name} onChange={(e) => setName(e.target.value)} /></Field>
            <Field label={t("auth.email")} htmlFor="email" error={errs.email}><input id="email" data-testid="email" type="email" required autoComplete="email" className="input" value={email} onChange={(e) => setEmail(e.target.value)} /></Field>
            <Field label={t("auth.password")} htmlFor="password" hint={t("auth.passwordHelp")} error={errs.password}><input id="password" data-testid="password" type="password" required minLength={8} autoComplete="new-password" className="input" value={password} onChange={(e) => setPassword(e.target.value)} /></Field>
            <Field label={t("onboarding.language")} htmlFor="lang">
              <select id="lang" className="input" value={language} onChange={(e) => setLang(e.target.value as Lang)}>
                {LANGS.map((l) => <option key={l} value={l}>{t(`lang.${l}`)}</option>)}
              </select>
            </Field>
            <button className="btn-primary w-full" disabled={busy} data-testid="submit">{busy ? <Spinner className="text-white" /> : t("auth.register")}</button>
          </form>
          <p className="mt-4 text-center text-sm text-muted">{t("auth.haveAccount")} <Link to="/login" className="font-semibold text-accent">{t("auth.signIn")}</Link></p>
        </Card>
      </main>
      <Toasts />
    </div>
  );
}
