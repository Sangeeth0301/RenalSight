import { Activity, FileText, Hourglass, Send } from "lucide-react";
import { useTranslation } from "react-i18next";
import { Link, useNavigate } from "react-router-dom";
import { LivingKidney } from "@/components/LivingKidney";
import { Card, Chip, EmptyState, ErrorState, LoadingBlock, PageHeader, SeverityMeter, UrgentBanner, Disclaimer } from "@/components/ui";
import { ApiError } from "@/lib/api";
import { useMyKidney } from "@/lib/hooks";
import { fmtDate, fmtNumber, stageColor } from "@/lib/utils";
import { HeartPulse } from "lucide-react";

export default function KidneyPage() {
  const { t, i18n } = useTranslation();
  const nav = useNavigate();
  const q = useMyKidney();

  if (q.isLoading) return <LoadingBlock rows={4} />;
  if (q.error instanceof ApiError && q.error.status === 422)
    return <EmptyState title={t("kidney.profileNeeded")} action={<Link to="/onboarding" className="btn-primary">{t("onboarding.title")}</Link>} icon={<HeartPulse className="h-7 w-7" />} />;
  if (q.error) return <ErrorState error={q.error} onRetry={() => q.refetch()} />;
  const k = q.data!;
  if (!k.has_data)
    return (
      <>
        <PageHeader title={t("kidney.title")} />
        <EmptyState title={t("kidney.noData")} action={<Link to="/reports" className="btn-primary" data-testid="add-lab">{t("kidney.addLab")}</Link>} icon={<FileText className="h-7 w-7" />} />
      </>
    );

  const topWounds = [...k.wounds].filter((w) => w.level > 0).sort((a, b) => b.level - a.level);
  return (
    <>
      {k.urgent && <UrgentBanner><Link to="/chat" className="btn-danger">{t("kidney.contactDoctor")}</Link></UrgentBanner>}
      <PageHeader title={t("kidney.title")} subtitle={k.as_of ? t("kidney.asOf", { date: fmtDate(k.as_of, i18n.language) }) : undefined} />
      <div className="grid gap-6 lg:grid-cols-[420px_minmax(0,1fr)]">
        <Card className="flex flex-col items-center">
          <LivingKidney state={k} size="lg" interactive />
          <p className="mt-3 text-center text-sm text-muted">{t("kidney.tapWound")}</p>
        </Card>
        <div className="space-y-4">
          <Card>
            <div className="flex flex-wrap items-center gap-3">
              <span className="chip text-white" style={{ background: stageColor(k.g_stage) }} data-testid="stage-chip">{t(`gStage.${k.g_stage}`)}</span>
              <Chip tone="accent">{t(`stages.${k.stage_name}`)}</Chip>
              {k.a_category && <Chip tone="slate">{k.a_category}</Chip>}
            </div>
            <div className="mt-4 grid grid-cols-2 gap-4">
              <div><p className="text-sm text-muted">{t("kidney.egfr")}</p><p className="text-3xl font-extrabold" data-testid="egfr">{fmtNumber(k.egfr, i18n.language)}</p></div>
              <div><p className="text-sm text-muted">{t("kidney.severity")}</p><p className="text-3xl font-extrabold">{Math.round(k.severity)}%</p></div>
            </div>
            <div className="mt-3"><SeverityMeter value={k.severity} /></div>
            <p className="mt-4 text-lg">{t(`stageDesc.${k.stage_name}`)}</p>
          </Card>
          {topWounds.length > 0 && (
            <Card>
              <h2 className="mb-3 text-lg font-bold">{t("kidney.healTips")}</h2>
              <ul className="space-y-3">
                {topWounds.map((w) => (
                  <li key={w.code} className="rounded-xl border border-line p-3">
                    <div className="flex items-center justify-between gap-2"><p className="font-semibold">{t(`wounds.${w.code}.title`)}</p><div className="w-28"><SeverityMeter value={w.level * 100} /></div></div>
                    <p className="mt-1 text-sm text-muted">{t(`wounds.${w.code}.cause`)}</p>
                    <p className="mt-1 text-sm">{t(`wounds.${w.code}.tip`)}</p>
                  </li>
                ))}
              </ul>
            </Card>
          )}
          <div className="flex flex-wrap gap-3">
            <button className="btn-primary" onClick={() => nav("/chat?share=kidney")}><Send className="h-4 w-4" />{t("kidney.shareWithDoctor")}</button>
            <Link to="/reports" className="btn-outline"><FileText className="h-4 w-4" />{t("labs.add")}</Link>
            <Link to="/forecast" className="btn-outline"><Hourglass className="h-4 w-4" />{t("nav.timeMachine")}</Link>
            <Link to="/buddy" className="btn-outline"><Activity className="h-4 w-4" />{t("nav.nephroBuddy")}</Link>
          </div>
        </div>
      </div>
      <Disclaimer />
    </>
  );
}
