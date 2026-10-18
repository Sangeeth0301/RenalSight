import { useMutation, useQuery } from "@tanstack/react-query";
import { Megaphone } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import { Card, Field, Spinner, useNotify } from "./ui";
import { api, type CampPlan } from "@/lib/api";
import { fmtNumber } from "@/lib/utils";

const REGIONS: [string, string][] = [["IND", "India"], ["IN-TN", "Tamil Nadu"], ["IN-WB", "West Bengal"], ["IN-AP", "Andhra Pradesh"], ["IN-TG", "Telangana"], ["IN-KA", "Karnataka"]];

/** Screening-camp planner and overdue-patient list (doctors and admins). Plans are proposals: a human approves them in the Helper inbox. */
export function OutreachCard({ defaultRegion = "IND" }: { defaultRegion?: string }) {
  const { t } = useTranslation();
  const notify = useNotify();
  const [region, setRegion] = useState(defaultRegion);
  const [target, setTarget] = useState("2000");
  const [perCamp, setPerCamp] = useState("200");
  const [plan, setPlan] = useState<CampPlan | null>(null);
  const overdue = useQuery({ queryKey: ["outreach", "overdue"], queryFn: () => api.outreachOverdue() });
  const make = useMutation({
    mutationFn: () => api.outreachPlan({ region, target_people: Number(target), people_per_camp_day: Number(perCamp) }),
    onSuccess: (r) => { setPlan(r.plan); notify.ok(t("doctor.outreachNeedsApproval")); },
    onError: (e) => notify.error(e),
  });
  return (
    <Card data-testid="outreach-card">
      <h2 className="mb-3 flex items-center gap-2 text-lg font-bold"><Megaphone className="h-5 w-5 text-accent" />{t("doctor.outreach")}</h2>
      <div className="grid gap-3 sm:grid-cols-4">
        <Field label={t("doctor.outreachRegion")}><select className="input" value={region} onChange={(e) => setRegion(e.target.value)} data-testid="outreach-region">{REGIONS.map(([c, n]) => <option key={c} value={c}>{n}</option>)}</select></Field>
        <Field label={t("doctor.outreachTarget")}><input className="input" type="number" min={100} value={target} onChange={(e) => setTarget(e.target.value)} data-testid="outreach-target" /></Field>
        <Field label={t("doctor.outreachPerCamp")}><input className="input" type="number" min={20} value={perCamp} onChange={(e) => setPerCamp(e.target.value)} /></Field>
        <div className="flex items-end"><button className="btn-primary w-full" disabled={make.isPending} onClick={() => make.mutate()} data-testid="outreach-make">{make.isPending ? <Spinner className="text-white" /> : t("doctor.outreachPlan")}</button></div>
      </div>
      {plan && (
        <div className="mt-4 space-y-2 rounded-xl2 bg-slate-50 p-4 text-sm" data-testid="outreach-plan">
          <p className="font-bold">{plan.region_name}: {plan.camp_days} camp day(s) · {fmtNumber(plan.target_people, "en", { maximumFractionDigits: 0 })} people · ~{plan.expected_with_kidney_disease} expected with kidney disease</p>
          <p className="font-semibold">{t("doctor.outreachChecklist")}</p>
          <ul className="list-disc pl-5">{plan.checklist.map((c) => <li key={c}>{c}</li>)}</ul>
          <p className="text-xs text-muted">{plan.assumptions.join(" ")}</p>
          <Link to="/inbox" className="font-semibold text-accent underline">{t("nav.agentInbox")} →</Link>
        </div>
      )}
      <h3 className="mb-2 mt-5 font-bold">{t("doctor.overdue")} ({overdue.data?.count ?? 0})</h3>
      {(overdue.data?.overdue ?? []).length === 0 ? <p className="text-sm text-muted">{t("app.noData")}</p> : (
        <ul className="divide-y divide-line rounded-xl border border-line text-sm" data-testid="overdue-list">{overdue.data!.overdue.map((o) => (
          <li key={o.patient_id} className="flex items-center justify-between px-3 py-2"><Link to={`/doctor/patients/${o.patient_id}`} className="font-semibold text-accent hover:underline">{o.name}</Link><span className="text-muted">{o.days_late > 0 ? `${o.days_late} d late` : `due ${o.due}`}</span></li>
        ))}</ul>
      )}
    </Card>
  );
}
