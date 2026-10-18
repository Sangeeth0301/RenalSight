import { useQuery } from "@tanstack/react-query";
import { ExternalLink, Search } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Card, Chip, EmptyState, ErrorState, LoadingBlock, PageHeader, useDebounced } from "@/components/ui";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";

export default function Research() {
  const { t } = useTranslation();
  const [q, setQ] = useState("");
  const [type, setType] = useState<string | undefined>();
  const dq = useDebounced(q, 250);
  const res = useQuery({ queryKey: ["research", dq, type], queryFn: () => api.researchSearch({ q: dq, type }), placeholderData: (p) => p });
  return (
    <>
      <PageHeader title={t("research.title")} subtitle={t("research.subtitle")} />
      <div className="mb-4 flex flex-wrap items-center gap-3">
        <div className="relative min-w-[240px] flex-1"><Search className="absolute left-3 top-3 h-5 w-5 text-muted" /><input data-testid="research-search" className="input !pl-10" placeholder={t("research.search")} value={q} onChange={(e) => setQ(e.target.value)} /></div>
        {([undefined, "guideline", "study", "trial"] as const).map((x) => <button key={x ?? "all"} onClick={() => setType(x)} className={cn("chip !px-3 !py-2 text-sm", type === x ? "bg-accent text-white" : "bg-slate-100 hover:bg-accent-soft")}>{x ? t(`research.types.${x}`) : t("research.all")}</button>)}
      </div>
      {res.isLoading ? <LoadingBlock /> : res.error ? <ErrorState error={res.error} onRetry={() => res.refetch()} /> : (res.data?.results ?? []).length === 0 ? <EmptyState title={t("research.none")} /> : (
        <div className="grid gap-4 md:grid-cols-2" data-testid="research-results">
          {res.data!.results.map((r) => (
            <Card key={r.id} className="flex flex-col gap-2" data-testid="research-item">
              <div className="flex flex-wrap items-center gap-2"><Chip tone={r.type === "guideline" ? "ok" : r.type === "trial" ? "info" : "slate"}>{t(`research.types.${r.type}`, { defaultValue: r.type })}</Chip><span className="text-sm text-muted">{r.year}</span></div>
              <p className="font-bold leading-snug">{r.title}</p>
              <p className="text-sm text-muted">{r.source}</p>
              <p className="text-sm">{r.summary}</p>
              <div className="mt-auto flex flex-wrap items-center gap-2 pt-1">{r.tags.slice(0, 4).map((x) => <span key={x} className="chip bg-slate-100 text-slate-600">{x}</span>)}
                <a className="btn-soft ml-auto !min-h-[38px] text-sm" href={r.url} target="_blank" rel="noopener noreferrer">{t("research.open")}<ExternalLink className="h-4 w-4" /></a></div>
            </Card>
          ))}
        </div>
      )}
      <p className="mt-6 text-center text-xs text-muted">{res.data?.note ?? t("research.note")}</p>
    </>
  );
}
