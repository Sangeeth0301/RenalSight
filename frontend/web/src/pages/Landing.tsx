import { motion } from "framer-motion";
import { Bot, Heart, Hourglass, Building2, Share2, HeartPulse, Languages, MapPinned, ShieldCheck } from "lucide-react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import { LivingKidney, NO_STATE } from "@/components/LivingKidney";
import { PublicBar } from "@/components/Layout";
import { Disclaimer } from "@/components/ui";
import { Toasts } from "@/components/ui";
import type { KidneyState } from "@/lib/api";
import { useEffect, useState } from "react";

const DEMO: KidneyState[] = [
  NO_STATE,
  { ...NO_STATE, g_stage: "G3a", visual_stage: 3, stage_name: "scarred", severity: 45, theme: "watch", shrink: 0.86, pulse: "slow", wounds: [{ code: "cracks", level: 0.4, cause: "low_egfr", value: 52 }, { code: "veins", level: 0.3, cause: "high_bp", value: 138 }] },
  { ...NO_STATE, g_stage: "G4", visual_stage: 4, stage_name: "wounded", severity: 74, theme: "critical", shrink: 0.79, pulse: "irregular", wounds: [{ code: "cracks", level: 0.8, cause: "low_egfr", value: 24 }, { code: "leak", level: 0.6, cause: "albuminuria", value: 420 }, { code: "veins", level: 0.6, cause: "high_bp", value: 156 }] },
];

export default function Landing() {
  const { t } = useTranslation();
  const [i, setI] = useState(0);
  useEffect(() => { const id = setInterval(() => setI((x) => (x + 1) % DEMO.length), 3800); return () => clearInterval(id); }, []);
  const features = [
    { icon: HeartPulse, title: t("landing.f1Title"), body: t("landing.f1Body") },
    { icon: Hourglass, title: t("landing.f2Title"), body: t("landing.f2Body") },
    { icon: ShieldCheck, title: t("landing.f3Title"), body: t("landing.f3Body") },
    { icon: Languages, title: t("landing.f4Title"), body: t("landing.f4Body") },
  ];
  return (
    <div className="min-h-full">
      <PublicBar />
      <main>
        <section className="mx-auto grid max-w-[1200px] items-center gap-8 px-5 py-12 md:grid-cols-2 md:py-20">
          <motion.div initial={{ opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5 }}>
            <p className="chip mb-4 bg-accent-soft text-ink">{t("app.tagline")}</p>
            <h1 className="font-display text-4xl font-extrabold leading-tight tracking-tight sm:text-5xl"><span className="text-gradient">{t("landing.heroTitle")}</span></h1>
            <p className="mt-5 max-w-xl text-lg text-muted">{t("landing.heroSub")}</p>
            <div className="mt-8 flex flex-wrap gap-3">
              <Link to="/register" className="btn-primary text-lg" data-testid="cta">{t("landing.cta")}</Link>
              <Link to="/login" className="btn-outline">{t("landing.signIn")}</Link>
              <Link to="/register?role=doctor" className="btn-ghost">{t("landing.imDoctor")}</Link>
            </div>
            <Link to="/pulse" className="mt-6 inline-flex items-center gap-2 font-semibold text-accent hover:underline"><MapPinned className="h-5 w-5" />{t("nav.populationPulse")}</Link>
          </motion.div>
          <motion.div initial={{ opacity: 0, scale: 0.94 }} animate={{ opacity: 1, scale: 1 }} transition={{ duration: 0.6, delay: 0.1 }} className="relative">
            <div className="card ring-glow mx-auto max-w-md p-6 animate-floaty">
              <LivingKidney state={DEMO[i]} size="lg" showEcg />
              <p className="mt-3 text-center font-semibold">{t(`stages.${DEMO[i].stage_name}`)}</p>
              <p className="text-center text-sm text-muted">{t(`stageDesc.${DEMO[i].stage_name}`)}</p>
            </div>
          </motion.div>
        </section>
        <section className="mx-auto max-w-[1200px] px-5 pb-16">
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {features.map((f, idx) => (
              <motion.div key={f.title} className="card p-5" initial={{ opacity: 0, y: 18 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }} transition={{ delay: idx * 0.07 }}>
                <div className="mb-3 grid h-12 w-12 place-items-center rounded-xl2 bg-accent-soft text-accent"><f.icon className="h-6 w-6" /></div>
                <h3 className="text-lg font-bold">{f.title}</h3>
                <p className="mt-1 text-muted">{f.body}</p>
              </motion.div>
            ))}
          </div>
          <div className="mt-10 grid gap-4 md:grid-cols-3">
            {[
              { icon: Heart, title: "Find a kidney donor", body: "Post a verified request, check blood-group compatibility and let your circle help. Never any payment." },
              { icon: Share2, title: "One-click WhatsApp appeals", body: "Type the hospital, patient and blood group. We write a polished appeal and open WhatsApp for you." },
              { icon: Building2, title: "Built for hospitals", body: "Hospital directory, coordinator desk, dialysis seat board, FHIR export and referral letters." },
            ].map((f, idx) => (
              <motion.div key={f.title} className="bento" initial={{ opacity: 0, y: 18 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }} transition={{ delay: idx * 0.08 }}>
                <div className="mb-3 grid h-12 w-12 place-items-center rounded-xl2 text-white" style={{ backgroundImage: "linear-gradient(135deg,var(--accent),var(--accent-2))" }}><f.icon className="h-6 w-6" /></div>
                <h3 className="font-display text-lg font-bold">{f.title}</h3>
                <p className="mt-1 text-muted">{f.body}</p>
              </motion.div>
            ))}
          </div>
          <div className="card mt-8 flex flex-wrap items-center gap-4 p-6">
            <Bot className="h-8 w-8 text-accent" />
            <p className="flex-1 text-lg font-semibold">{t("buddy.subtitle")}</p>
            <Link to="/register" className="btn-soft">{t("landing.cta")}</Link>
          </div>
          <Disclaimer />
        </section>
      </main>
      <Toasts />
    </div>
  );
}
