import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, Circle } from "lucide-react";
import { useTranslation } from "react-i18next";
import { Card, ErrorState, LoadingBlock, PageHeader, Progress, useNotify } from "@/components/ui";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";

export default function Journey() {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const notify = useNotify();
  const q = useQuery({ queryKey: ["tx", "journey"], queryFn: () => api.journey() });
  const set = useMutation({ mutationFn: (v: { key: string; done: boolean }) => api.setStep(v.key, { done: v.done }), onSuccess: (j) => qc.setQueryData(["tx", "journey"], j), onError: (e) => notify.error(e) });
  if (q.isLoading) return <LoadingBlock rows={5} />;
  if (q.error || !q.data) return <ErrorState error={q.error} onRetry={() => void q.refetch()} />;
  const j = q.data;
  return (
    <div className="space-y-5">
      <PageHeader title={t("transplant.journeyTitle", "Your transplant journey")} subtitle={t("transplant.journeySubtitle", "Tick each step as the hospital completes it. It helps your family know what comes next.")} />
      <Card>
        <div className="flex items-center gap-4"><p className="font-display text-3xl font-extrabold text-gradient" data-testid="journey-progress">{j.progress}%</p><div className="flex-1"><Progress value={j.progress} /></div></div>
      </Card>
      <ol className="space-y-3">
        {j.steps.map((s, i) => (
          <li key={s.key}>
            <button onClick={() => set.mutate({ key: s.key, done: !s.done })} data-testid={`step-${s.key}`} className={cn("card flex w-full items-start gap-4 p-4 text-left", j.next === s.key && "ring-glow")}>
              <span className={cn("mt-0.5 grid h-8 w-8 shrink-0 place-items-center rounded-full border-2 font-bold", s.done ? "border-transparent text-white" : "border-line text-muted")} style={s.done ? { backgroundImage: "linear-gradient(135deg,var(--ok),var(--accent))" } : undefined}>{s.done ? <Check className="h-4 w-4" /> : i + 1}</span>
              <span className="min-w-0 flex-1"><span className="block font-semibold">{s.title}{j.next === s.key && <span className="chip ml-2 bg-accent-soft text-ink">{t("transplant.next", "Next")}</span>}</span><span className="mt-0.5 block text-sm text-muted">{s.body}</span></span>
              {!s.done && <Circle className="mt-1 h-4 w-4 text-muted" />}
            </button>
          </li>
        ))}
      </ol>
    </div>
  );
}
