import { useQuery } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { AlertTriangle, Check, Droplets, Dumbbell, HeartPulse, Pill, Salad, Stethoscope, Syringe, Thermometer, type LucideIcon } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import { Card, DemoBadge, Disclaimer, EmptyState, ErrorState, LoadingBlock, PageHeader, Progress } from "@/components/ui";
import { api, type CarePlanItem } from "@/lib/api";
import { cn, tx } from "@/lib/utils";
import { useSession } from "@/store/session";

const ICON: Record<string, LucideIcon> = { urgent: AlertTriangle, diet: Salad, fluids: Droplets, blood_pressure: HeartPulse, blood_sugar: Syringe, medicines: Pill, activity: Dumbbell, monitoring: Stethoscope, warning_signs: Thermometer };
type Lane = "critical" | "quick" | "daily";
const QUICK = new Set(["avoid_nsaids", "avoid_herbal", "sick_day", "diet_salt", "no_tobacco"]);

interface Goal { id: string; sec: string; item: CarePlanItem; lane: Lane }

export default function Care() {
  const { t } = useTranslation();
  const user = useSession((s) => s.user)!;
  const q = useQuery({ queryKey: ["careplan"], queryFn: () => api.myCarePlan() });
  const key = `care_done_${user.id}`;
  const [done, setDone] = useState<Record<string, boolean>>(() => { try { return JSON.parse(localStorage.getItem(key) ?? "{}"); } catch { return {}; } });
  useEffect(() => { try { localStorage.setItem(key, JSON.stringify(done)); } catch { /* ignore */ } }, [done, key]);

  const goals = useMemo<Goal[]>(() => {
    const out: Goal[] = [];
    const secs = q.data?.sections ?? {};
    for (const [sec, items] of Object.entries(secs)) {
      for (const item of items) {
        const lane: Lane = sec === "urgent" || sec === "warning_signs" ? "critical" : sec === "medicines" || QUICK.has(item.code) ? "quick" : "daily";
        out.push({ id: item.code, sec, item, lane });
      }
    }
    return out;
  }, [q.data]);

  if (q.isLoading) return <LoadingBlock rows={4} />;
  if (q.error) return <ErrorState error={q.error} onRetry={() => q.refetch()} />;
  if (!q.data?.has_data)
    return (<><PageHeader title={t("carePlan.title")} /><EmptyState title={t("rx.needLabs")} action={<Link className="btn-primary" to="/reports">{t("labs.add")}</Link>} /></>);

  const total = goals.filter((g) => g.lane !== "critical").length;
  const completed = goals.filter((g) => g.lane !== "critical" && done[g.id]).length;
  const lanes: Lane[] = ["critical", "quick", "daily"];
  const tone: Record<Lane, string> = { critical: "border-rose-300 bg-rose-50", quick: "border-amber-300 bg-amber-50", daily: "border-line bg-white" };

  return (
    <>
      <PageHeader title={t("carePlan.title")} subtitle={t("carePlan.intro")} right={<div className="flex items-center gap-3"><DemoBadge /><div className="w-40"><Progress value={completed} max={Math.max(total, 1)} tone="ok" /><p className="mt-1 text-right text-xs text-muted" data-testid="care-progress">{completed}/{total}</p></div></div>} />
      <div className="space-y-8">
        {lanes.map((lane) => {
          const list = goals.filter((g) => g.lane === lane);
          if (!list.length) return null;
          return (
            <section key={lane} data-testid={`lane-${lane}`}>
              <h2 className="mb-3 text-lg font-bold">{t(`carePlan.careLabGroups.${lane}`)}</h2>
              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                {list.map((g, i) => {
                  const Icon = ICON[g.sec] ?? HeartPulse;
                  const isDone = !!done[g.id];
                  return (
                    <motion.div key={g.id} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.03 }}
                      className={cn("flex flex-col gap-2 rounded-xl2 border-2 p-4 transition", tone[lane], isDone && "opacity-60")}>
                      <div className="flex items-center gap-2 text-sm font-bold uppercase tracking-wide text-muted"><Icon className="h-4 w-4" />{t(`carePlan.sections.${g.sec}`)}</div>
                      <p className="flex-1">{tx(t, `carePlan.items.${g.item.code}`, g.item.params)}</p>
                      {lane !== "critical" && (
                        <button className={cn("btn min-h-[40px]", isDone ? "bg-emerald-600 text-white" : "bg-white border border-line")} onClick={() => setDone({ ...done, [g.id]: !isDone })} data-testid={`tick-${g.id}`} aria-pressed={isDone}>
                          <Check className="h-4 w-4" />{isDone ? t("app.yes") : t("app.next")}
                        </button>
                      )}
                    </motion.div>
                  );
                })}
              </div>
            </section>
          );
        })}
      </div>
      <div className="mt-8 flex flex-wrap gap-3"><Link to="/rx" className="btn-primary">{t("rx.title")}</Link><Link to="/chat" className="btn-outline">{t("chat.openWithDoctor")}</Link></div>
      <Disclaimer />
    </>
  );
}
