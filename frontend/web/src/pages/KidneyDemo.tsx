import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { PublicBar } from "@/components/Layout";
import { LivingKidney, NO_STATE } from "@/components/LivingKidney";
import { Card, PageHeader, SeverityMeter, Toasts, useDebounced } from "@/components/ui";
import { api, auth } from "@/lib/api";

/** Public preview route: move the sliders and watch the kidney change at every stage. */
export default function KidneyDemo() {
  const { t } = useTranslation();
  const [v, setV] = useState({ egfr: 75, acr: 20, sbp: 125, hgb: 13.5, potassium: 4.4 });
  const d = useDebounced(v, 250);
  const q = useQuery({ queryKey: ["kidney-demo", d], queryFn: () => api.kidneyState({ ...d, sex: "male" }), enabled: !!auth.token, placeholderData: (p) => p });
  const state = q.data ?? NO_STATE;
  const sliders: { k: keyof typeof v; min: number; max: number; step: number; label: string }[] = [
    { k: "egfr", min: 5, max: 110, step: 1, label: "eGFR" }, { k: "acr", min: 0, max: 3000, step: 10, label: "ACR mg/g" },
    { k: "sbp", min: 90, max: 200, step: 1, label: t("labs.sbp") }, { k: "hgb", min: 6, max: 16, step: 0.1, label: t("labs.hgb") },
    { k: "potassium", min: 3, max: 7, step: 0.1, label: t("labs.potassium") },
  ];
  return (
    <div className="min-h-full bg-bg">
      <PublicBar />
      <main className="mx-auto max-w-4xl px-4 py-8">
        <PageHeader title="Living kidney demo" subtitle={auth.token ? undefined : "Sign in to use the live sliders (they call the real API)."} />
        <div className="grid gap-6 md:grid-cols-2">
          <Card><LivingKidney state={state} size="lg" interactive /></Card>
          <Card className="space-y-4">
            {sliders.map((s) => (
              <label key={s.k} className="block"><span className="label">{s.label}: <b>{v[s.k]}</b></span>
                <input type="range" className="w-full accent-[var(--accent)]" min={s.min} max={s.max} step={s.step} value={v[s.k]} onChange={(e) => setV({ ...v, [s.k]: Number(e.target.value) })} />
              </label>
            ))}
            <p className="text-sm">{t(`stages.${state.stage_name}`)} - {state.g_stage}</p>
            <SeverityMeter value={state.severity} />
          </Card>
        </div>
      </main>
      <Toasts />
    </div>
  );
}
