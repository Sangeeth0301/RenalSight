import { useMutation, useQuery } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { ArrowRight, Building2, DoorOpen, FileText, FlaskConical, Hourglass, MapPinned, MessageCircle, Pill, Send } from "lucide-react";
import { useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";
import { Link, useNavigate } from "react-router-dom";
import { LivingKidney } from "@/components/LivingKidney";
import { Card, Chip, DemoBadge, Disclaimer, Spinner, UrgentBanner, useNotify } from "@/components/ui";
import { api, type CarePlanItem } from "@/lib/api";
import { isPatientLike, useMyKidney } from "@/lib/hooks";
import { currentLang } from "@/i18n";
import { relTime, tx } from "@/lib/utils";
import { useSession } from "@/store/session";
import { Tx } from "@/lib/translate";

const MODULES = [
  { to: "/reports", key: "reportGuidance", icon: FileText, only: "patient" },
  { to: "/kidney", key: "livingKidney", icon: FlaskConical },
  { to: "/forecast", key: "timeMachine", icon: Hourglass, only: "patient" },
  { to: "/care", key: "careLab", icon: FlaskConical, only: "patient" },
  { to: "/rx", key: "rxStudio", icon: Pill, only: "patient" },
  { to: "/chat", key: "directLine", icon: MessageCircle },
  { to: "/rooms", key: "consultRoom", icon: DoorOpen },
  { to: "/pulse", key: "populationPulse", icon: MapPinned },
  { to: "/care-hub", key: "careHub", icon: Building2 },
] as const;

export default function Home() {
  const { t, i18n } = useTranslation();
  const nav = useNavigate();
  const user = useSession((s) => s.user)!;
  const notify = useNotify();
  const kq = useMyKidney();
  const k = kq.data;
  const [text, setText] = useState("");
  const [answer, setAnswer] = useState<{ reply: string; ai_online: boolean } | null>(null);

  const notes = useQuery({ queryKey: ["notifications", "all"], queryFn: () => api.notifications(), refetchInterval: 30000 });
  const plan = useQuery({ queryKey: ["careplan"], queryFn: () => api.myCarePlan(), enabled: user.role === "patient" });
  const rx = useQuery({ queryKey: ["rx", "list"], queryFn: () => api.rxList(), enabled: user.role === "patient" });
  const buddyStatus = useQuery({ queryKey: ["buddy", "status"], queryFn: () => api.buddyStatus(), refetchInterval: 60000 });

  const ask = useMutation({
    mutationFn: (m: string) => api.buddyChat(m, currentLang()),
    onSuccess: (r) => setAnswer({ reply: r.reply, ai_online: r.ai_online }),
    onError: (e) => notify.error(e),
  });
  const submit = (e: FormEvent, preset?: string) => {
    e.preventDefault();
    const m = (preset ?? text).trim();
    if (!m) return;
    setText(preset ? "" : text);
    ask.mutate(m);
  };

  const tips: { sec: string; it: CarePlanItem }[] = [];
  if (plan.data?.has_data && plan.data.sections) {
    for (const sec of ["diet", "medicines", "activity"]) {
      const it = plan.data.sections[sec]?.[0];
      if (it) tips.push({ sec, it });
    }
  }
  const nextSteps: { text: string; to: string; tone?: "danger" }[] = [];
  if (user.role === "patient") {
    if (user.birth_year === null || user.sex === null) nextSteps.push({ text: t("kidney.profileNeeded"), to: "/onboarding" });
    if (k && !k.has_data) nextSteps.push({ text: t("kidney.addLab"), to: "/reports" });
    if (user.doctor_id === null) nextSteps.push({ text: t("rx.needDoctor"), to: "/settings" });
    if ((rx.data ?? []).some((r) => r.status === "submitted")) nextSteps.push({ text: t("rx.status.submitted"), to: "/rx" });
    for (const it of plan.data?.sections?.urgent ?? []) nextSteps.unshift({ text: tx(t, `carePlan.items.${it.code}`, it.params), to: "/care", tone: "danger" });
  }

  const suggestions = ["explain", "eat", "forecast"] as const;
  const visible = MODULES.filter((m) => !("only" in m) || m.only === user.role);

  return (
    <>
      {k?.has_data && k.urgent && <UrgentBanner><Link to="/chat" className="btn-danger">{t("kidney.contactDoctor")}</Link></UrgentBanner>}
      <div className="mb-5 flex flex-wrap items-center gap-3">
        <h1 className="text-2xl font-bold sm:text-3xl">{t("auth.welcome", { name: user.name })}</h1>
        {k?.has_data && <Chip tone="accent">{t(`gStage.${k.g_stage}`)} · {t(`stages.${k.stage_name}`)}</Chip>}
      </div>
      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_340px]">
        <div className="space-y-6">
          <Card className="overflow-hidden">
            <div className="grid items-center gap-5 sm:grid-cols-[240px_minmax(0,1fr)]">
              <div>
                {kq.isLoading ? <div className="skeleton mx-auto h-64 w-44" /> : k?.has_data
                  ? <Link to="/kidney" aria-label={t("nav.livingKidney")}><LivingKidney state={k} size="md" showEcg={false} /></Link>
                  : <div className="rounded-xl2 bg-accent-soft p-4 text-center"><p className="font-semibold">{t("kidney.noData")}</p><Link className="btn-primary mt-3" to="/reports">{t("kidney.addLab")}</Link></div>}
              </div>
              <div>
                <p className="mb-2 flex items-center gap-2 font-mono text-sm font-semibold text-accent">{">"} {t("nav.nephroBuddy")}</p>
                <form onSubmit={submit} className="flex gap-2">
                  <input data-testid="home-ask" className="input" placeholder={t("buddy.placeholder")} value={text} onChange={(e) => setText(e.target.value)} maxLength={1000} />
                  <button className="btn-primary !px-4" disabled={ask.isPending} aria-label={t("app.send")}>{ask.isPending ? <Spinner className="text-white" /> : <Send className="h-5 w-5" />}</button>
                </form>
                <div className="mt-3 flex flex-wrap gap-2">
                  {suggestions.map((s) => <button key={s} className="chip bg-slate-100 !px-3 !py-1.5 text-sm hover:bg-accent-soft" onClick={(e) => submit(e as any, t(`buddy.suggestions.${s}`))}>{t(`buddy.suggestions.${s}`)}</button>)}
                </div>
                {ask.isPending && <p className="mt-3 text-sm text-muted">{t("buddy.thinking")}</p>}
                {answer && (
                  <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="mt-3 rounded-xl2 bg-slate-50 p-3" data-testid="home-answer">
                    <Tx as="p" className="whitespace-pre-wrap" text={answer.reply} />
                    {!answer.ai_online && <p className="mt-2 text-xs text-muted">{t("app.basicMode")}</p>}
                    <button className="mt-2 inline-flex items-center gap-1 text-sm font-semibold text-accent" onClick={() => nav("/buddy")}>{t("app.learnMore")} <ArrowRight className="h-4 w-4" /></button>
                  </motion.div>
                )}
                {buddyStatus.data && !buddyStatus.data.ai_online && !answer && <p className="mt-3 text-xs text-muted">{t("app.basicMode")}</p>}
              </div>
            </div>
          </Card>

          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
            {visible.map((m, i) => (
              <motion.div key={m.key} initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.04 }}>
                <Link to={m.to} className="card group flex min-h-[110px] flex-col gap-2 p-4 transition hover:-translate-y-0.5 hover:shadow-lift">
                  <span className="grid h-10 w-10 place-items-center rounded-xl bg-accent-soft text-accent"><m.icon className="h-5 w-5" /></span>
                  <span className="font-semibold">{t(`nav.${m.key}`)}</span>
                </Link>
              </motion.div>
            ))}
          </div>
        </div>

        <aside className="space-y-4 lg:sticky lg:top-20 lg:self-start">
          <Card>
            <h2 className="mb-3 text-lg font-bold">{t("nav.notifications")}</h2>
            {notes.isLoading ? <div className="skeleton h-16" /> : (notes.data ?? []).length === 0 ? <p className="text-sm text-muted">{t("notifications.empty")}</p> : (
              <ul className="space-y-2">
                {(notes.data ?? []).slice(0, 5).map((n) => (
                  <li key={n.id} className="rounded-xl bg-slate-50 p-2">
                    <p className="text-sm font-semibold">{t(`notifications.kinds.${n.kind}`, { defaultValue: n.title })}</p>
                    <p className="text-xs text-muted">{relTime(n.created_at, i18n.language)}</p>
                  </li>
                ))}
              </ul>
            )}
            <Link to="/notifications" className="mt-3 block text-center text-sm font-semibold text-accent">{t("app.learnMore")}</Link>
          </Card>
          {nextSteps.length > 0 && (
            <Card>
              <h2 className="mb-3 text-lg font-bold">{t("app.next")}</h2>
              <ul className="space-y-2">
                {nextSteps.map((s, i) => (
                  <li key={i}><Link to={s.to} className={`block rounded-xl p-3 text-sm font-semibold ${s.tone === "danger" ? "bg-rose-50 text-rose-900" : "bg-accent-soft"}`}>{s.text}</Link></li>
                ))}
              </ul>
            </Card>
          )}
          {tips.length > 0 && (
            <Card>
              <h2 className="mb-3 text-lg font-bold">{t("carePlan.title")}</h2>
              <ul className="space-y-3">
                {tips.map(({ sec, it }) => (
                  <li key={it.code}><p className="text-xs font-bold uppercase text-muted">{t(`carePlan.sections.${sec}`)}</p><p className="text-sm">{tx(t, `carePlan.items.${it.code}`, it.params)}</p></li>
                ))}
              </ul>
              <Link to="/care" className="mt-3 block text-center text-sm font-semibold text-accent">{t("nav.careLab")}</Link>
            </Card>
          )}
          {!isPatientLike(user.role) && <DemoBadge />}
        </aside>
      </div>
      <Disclaimer />
    </>
  );
}
