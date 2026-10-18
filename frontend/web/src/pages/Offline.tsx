import { useQuery } from "@tanstack/react-query";
import { CloudOff, Printer } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import { Card, Chip, Disclaimer, EmptyState, ErrorState, LoadingBlock, PageHeader, Tabs } from "@/components/ui";
import { api } from "@/lib/api";
import { fmtNumber, tx } from "@/lib/utils";

type Doc = "diet" | "emergency" | "exercise" | "glossary";

export default function Offline() {
  const { t, i18n } = useTranslation();
  const [doc, setDoc] = useState<Doc>("diet");
  const plan = useQuery({ queryKey: ["careplan"], queryFn: () => api.myCarePlan() });
  const card = useQuery({ queryKey: ["emergency-card"], queryFn: () => api.emergencyCard() });

  return (
    <>
      <PageHeader title={t("offline.title")} subtitle={t("offline.subtitle")} chip={<Chip tone="ok"><CloudOff className="h-3.5 w-3.5" />{t("offline.cached")}</Chip>}
        right={<button className="btn-primary no-print" onClick={() => window.print()} data-testid="print"><Printer className="h-4 w-4" />{t("offline.print")}</button>} />
      <div className="no-print"><Tabs value={doc} onChange={setDoc} tabs={(["diet", "emergency", "exercise", "glossary"] as const).map((d) => ({ value: d, label: t(`offline.docs.${d}`) }))} /></div>

      {doc === "diet" && (
        <div className="space-y-4" data-testid="doc-diet">
          <h2 className="hidden text-2xl font-bold print:block">{t("offline.docs.diet")}</h2>
          <div className="grid gap-4 md:grid-cols-3">
            <Card className="border-emerald-300 bg-emerald-50"><h3 className="font-bold text-emerald-900">{t("offline.foodsLow")}</h3><p className="mt-2">{t("offline.foodsLowList")}</p></Card>
            <Card className="border-amber-300 bg-amber-50"><h3 className="font-bold text-amber-900">{t("offline.foodsHigh")}</h3><p className="mt-2">{t("offline.foodsHighList")}</p></Card>
            <Card className="border-rose-300 bg-rose-50"><h3 className="font-bold text-rose-900">{t("offline.foodsSalt")}</h3><p className="mt-2">{t("offline.foodsSaltList")}</p></Card>
          </div>
          {plan.data?.has_data && plan.data.sections && (
            <Card><h3 className="mb-2 text-lg font-bold">{t("carePlan.sections.diet")}</h3>
              <ul className="list-disc space-y-1 pl-5">{[...(plan.data.sections.diet ?? []), ...(plan.data.sections.fluids ?? [])].map((it) => <li key={it.code}>{tx(t, `carePlan.items.${it.code}`, it.params)}</li>)}</ul></Card>
          )}
        </div>
      )}

      {doc === "emergency" && (
        card.isLoading ? <LoadingBlock /> : card.error ? <ErrorState error={card.error} onRetry={() => card.refetch()} /> : !card.data?.g_stage ? <EmptyState title={t("offline.needLabs")} action={<Link to="/reports" className="btn-primary">{t("labs.add")}</Link>} /> : (
          <Card className="mx-auto max-w-xl border-2 border-rose-400 !p-0 overflow-hidden" data-testid="doc-emergency">
            <div className="bg-rose-600 px-5 py-3 text-white"><p className="text-xl font-extrabold">{t("offline.docs.emergency")}</p><p className="text-sm opacity-90">{t("offline.cardNote")}</p></div>
            <div className="space-y-3 p-5">
              <p className="text-2xl font-bold" data-testid="card-name">{card.data.name}</p>
              <p className="text-muted">{card.data.age ?? "-"} · {card.data.sex === "male" ? t("onboarding.male") : card.data.sex === "female" ? t("onboarding.female") : "-"}</p>
              <div className="flex flex-wrap gap-2"><span className="chip bg-rose-100 text-rose-800">{t(`gStage.${card.data.g_stage}`)}</span>{card.data.a_category && <span className="chip bg-slate-100">{card.data.a_category}</span>}
                {card.data.diabetes && <span className="chip bg-amber-100 text-amber-800">{t("onboarding.diabetes").split("(")[0]}</span>}{card.data.hypertension && <span className="chip bg-amber-100 text-amber-800">{t("onboarding.hypertension")}</span>}</div>
              <p>eGFR <b>{fmtNumber(card.data.egfr, i18n.language)}</b> · K+ <b>{fmtNumber(card.data.potassium, i18n.language)}</b></p>
              <div><p className="text-sm font-bold uppercase text-muted">{t("offline.cardDoctor")}</p><p>{card.data.doctor ? `Dr. ${card.data.doctor.name}${card.data.doctor.code ? ` (${card.data.doctor.code})` : ""}` : "-"}</p></div>
              <div><p className="text-sm font-bold uppercase text-muted">{t("offline.cardMeds")}</p>{card.data.medicines.length === 0 ? <p>{t("offline.cardNone")}</p> : <ul className="list-disc pl-5">{card.data.medicines.map((m) => <li key={m.name}>{m.name} {m.dose_mg} mg {m.times_per_day ? `x ${m.times_per_day}` : ""}</li>)}</ul>}</div>
              <p className="rounded-xl bg-rose-50 p-3 font-semibold text-rose-900">{t("offline.cardAvoid")}</p>
              <div><p className="text-sm font-bold uppercase text-muted">{t("offline.cardWarn")}</p><ul className="list-disc pl-5 text-sm">{card.data.warning_codes.map((c) => <li key={c}>{t(`carePlan.items.${c}`)}</li>)}</ul></div>
            </div>
          </Card>
        )
      )}

      {doc === "exercise" && (
        <Card data-testid="doc-exercise"><ul className="space-y-3 text-lg">{(["walk", "stretch", "lift", "rest"] as const).map((k) => <li key={k} className="flex gap-3"><span className="mt-1 grid h-7 w-7 shrink-0 place-items-center rounded-full bg-accent-soft font-bold">•</span>{t(`offline.exerciseList.${k}`)}</li>)}</ul></Card>
      )}

      {doc === "glossary" && (
        <Card data-testid="doc-glossary"><dl className="space-y-3">{(["egfr", "creatinine", "albuminuria", "potassium", "dialysis", "ckd"] as const).map((k) => <div key={k} className="rounded-xl bg-slate-50 p-3">{t(`offline.glossary.${k}`)}</div>)}</dl></Card>
      )}
      <Disclaimer />
    </>
  );
}
