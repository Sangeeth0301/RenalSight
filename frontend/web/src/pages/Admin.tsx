import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import { OutreachCard } from "@/components/OutreachCard";
import { Card, Chip, ErrorState, Field, LoadingBlock, PageHeader, Spinner, useNotify } from "@/components/ui";
import { api, type Lang, type ProviderKind } from "@/lib/api";
import { tx } from "@/lib/utils";

const TONE = { ready: "ok", cooldown: "warn", not_configured: "slate", always_available: "info" } as const;

export default function Admin() {
  const { t } = useTranslation();
  const notify = useNotify();
  const qc = useQueryClient();
  const reported = useQuery({ queryKey: ["admin", "reported"], queryFn: () => api.reportedPosts() });
  const providers = useQuery({ queryKey: ["care-hub", "providers", "admin"], queryFn: () => api.careProviders({}) });
  const restore = useMutation({ mutationFn: (id: number) => api.restorePost(id), onSuccess: () => void qc.invalidateQueries({ queryKey: ["admin", "reported"] }), onError: (e) => notify.error(e) });
  const removeProvider = useMutation({ mutationFn: (id: number) => api.deleteProvider(id), onSuccess: () => void qc.invalidateQueries({ queryKey: ["care-hub"] }), onError: (e) => notify.error(e) });
  const [np, setNp] = useState({ kind: "nephrologist" as ProviderKind, name: "", city: "", region: "IN-TN", phone: "", services: "", min_stage: "3", lang: "en" as Lang });
  const addProvider = useMutation({
    mutationFn: () => api.addProvider({ kind: np.kind, name: np.name, city: np.city, region: np.region, phone: np.phone, services: np.services, min_stage: Number(np.min_stage), languages: [np.lang] }),
    onSuccess: () => { notify.ok(t("app.save")); setNp({ ...np, name: "", city: "", phone: "", services: "" }); void qc.invalidateQueries({ queryKey: ["care-hub"] }); },
    onError: (e) => notify.error(e),
  });
  const runJobs = useMutation({ mutationFn: () => api.agentsRefresh(), onSuccess: (r) => notify.ok(JSON.stringify(r.created)), onError: (e) => notify.error(e) });
  const llm = useQuery({ queryKey: ["admin", "llm"], queryFn: () => api.llmStatus(), refetchInterval: 15000 });
  const regions = useQuery({ queryKey: ["pop", "regions"], queryFn: () => api.popRegions() });
  const tools = useQuery({ queryKey: ["admin", "tools"], queryFn: () => api.tools() });
  const [f, setF] = useState({ region: "IN-TN", year: String(new Date().getFullYear()), dialysis_stations: "", nephrologists: "", source: "" });
  const [saved, setSaved] = useState<string | null>(null);
  const save = useMutation({
    mutationFn: () => api.popSetCapacity({ region: f.region, year: Number(f.year), dialysis_stations: f.dialysis_stations ? Number(f.dialysis_stations) : undefined, nephrologists: f.nephrologists ? Number(f.nephrologists) : undefined, source: f.source }),
    onSuccess: () => { setSaved(f.region); notify.ok(t("app.save")); },
    onError: (e) => notify.error(e),
  });
  return (
    <>
      <PageHeader title={t("nav.adminPanel")} />
      <div className="space-y-6">
        <Card>
          <h2 className="mb-1 text-lg font-bold">{t("admin.llmTitle")}</h2>
          <p className="mb-3 text-sm text-muted">Providers are tried in order. When one runs out of quota the next takes over; the last one (rules) always works.</p>
          {llm.isLoading ? <LoadingBlock rows={2} /> : llm.error ? <ErrorState error={llm.error} onRetry={() => llm.refetch()} /> : (
            <div className="overflow-x-auto"><table className="w-full min-w-[620px] text-left text-sm" data-testid="llm-table">
              <thead className="text-xs uppercase text-muted"><tr><th className="py-2">{t("admin.provider")}</th><th>{t("admin.state")}</th><th>{t("admin.model")}</th><th>{t("admin.successes")}</th><th>{t("admin.failures")}</th><th>{t("admin.lastError")}</th></tr></thead>
              <tbody>{(llm.data ?? []).map((p) => (
                <tr key={p.provider} className="border-t border-line"><td className="py-2 font-semibold">{p.provider}</td>
                  <td><Chip tone={TONE[p.state]}>{p.state === "cooldown" ? tx(t, "admin.cooldown", { s: p.cooldown_seconds_left }) : t(`admin.states.${p.state}`)}</Chip></td>
                  <td>{p.model ?? "-"}</td><td>{p.successes ?? "-"}</td><td>{p.failures ?? "-"}</td><td className="max-w-[260px] truncate text-muted">{p.last_error ?? ""}</td></tr>
              ))}</tbody></table></div>
          )}
        </Card>
        <Card>
          <h2 className="mb-1 text-lg font-bold">{t("admin.capacityTitle")}</h2><p className="mb-3 text-sm text-muted">{t("admin.capacityHelp")}</p>
          <form onSubmit={(e: FormEvent) => { e.preventDefault(); save.mutate(); }} className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
            <Field label={t("admin.region")}><select data-testid="cap-region" className="input" value={f.region} onChange={(e) => setF({ ...f, region: e.target.value })}>{regions.data?.regions.map((r) => <option key={r.code} value={r.code}>{r.name}</option>)}</select></Field>
            <Field label={t("admin.year")}><input className="input" type="number" min={2000} max={2050} value={f.year} onChange={(e) => setF({ ...f, year: e.target.value })} /></Field>
            <Field label={t("admin.stations")}><input data-testid="cap-stations" className="input" type="number" min={0} value={f.dialysis_stations} onChange={(e) => setF({ ...f, dialysis_stations: e.target.value })} /></Field>
            <Field label={t("admin.nephrologists")}><input data-testid="cap-neph" className="input" type="number" min={0} value={f.nephrologists} onChange={(e) => setF({ ...f, nephrologists: e.target.value })} /></Field>
            <Field label={t("admin.source")}><input data-testid="cap-source" className="input" minLength={5} required value={f.source} onChange={(e) => setF({ ...f, source: e.target.value })} /></Field>
            <button className="btn-primary sm:col-span-2 lg:col-span-5" disabled={save.isPending} data-testid="cap-save">{save.isPending ? <Spinner className="text-white" /> : t("app.save")}</button>
          </form>
          {saved && <Link className="mt-3 inline-block font-semibold text-accent" to={`/pulse?region=${saved}`}>→ {t("nav.populationPulse")}</Link>}
        </Card>
        <Card>
          <h2 className="mb-3 text-lg font-bold">{t("admin.tools")}</h2>
          {tools.isLoading ? <LoadingBlock rows={2} /> : (
            <div className="overflow-x-auto"><table className="w-full min-w-[560px] text-left text-sm"><thead className="text-xs uppercase text-muted"><tr><th className="py-2">Tool</th><th>Module</th><th>Writes</th><th>Description</th></tr></thead>
              <tbody>{(tools.data ?? []).map((x) => <tr key={x.name} className="border-t border-line align-top"><td className="py-2 font-mono font-semibold">{x.name}</td><td>{x.module}</td><td>{x.writes ? "yes" : "no"}</td><td className="text-muted">{x.description}</td></tr>)}</tbody></table></div>
          )}
        </Card>
        <OutreachCard />
        <Card>
          <div className="mb-2 flex items-center justify-between"><h2 className="text-lg font-bold">{t("admin.reported")}</h2>
            <button className="btn-outline !min-h-[36px] text-sm" onClick={() => runJobs.mutate()} disabled={runJobs.isPending} data-testid="run-jobs">{t("admin.runJobs")}</button></div>
          {(reported.data ?? []).length === 0 ? <p className="text-muted" data-testid="no-reports">{t("admin.noReports")}</p> : (
            <ul className="space-y-2" data-testid="reported-list">{reported.data!.map((p) => (
              <li key={p.id} className="flex items-start justify-between gap-3 rounded-xl border border-line p-3"><div><p className="text-sm text-muted">{p.author} · {p.reports} reports {p.hidden ? <Chip tone="danger">hidden</Chip> : null}</p><p>{p.body}</p></div>
                <button className="btn-soft !min-h-[36px] text-sm" onClick={() => restore.mutate(p.id)}>{t("admin.restore")}</button></li>
            ))}</ul>
          )}
        </Card>
        <Card>
          <h2 className="mb-3 text-lg font-bold">{t("admin.providers")}</h2>
          <form className="mb-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4" onSubmit={(e: FormEvent) => { e.preventDefault(); addProvider.mutate(); }}>
            <Field label={t("admin.providerKind")}><select className="input" value={np.kind} onChange={(e) => setNp({ ...np, kind: e.target.value as ProviderKind })}>{(["nephrologist", "dialysis", "lab", "pharmacy"] as const).map((k) => <option key={k} value={k}>{t(`hub.kinds.${k}`)}</option>)}</select></Field>
            <Field label={t("admin.providerName")}><input data-testid="prov-name" required minLength={3} className="input" value={np.name} onChange={(e) => setNp({ ...np, name: e.target.value })} /></Field>
            <Field label={t("admin.providerCity")}><input className="input" value={np.city} onChange={(e) => setNp({ ...np, city: e.target.value })} /></Field>
            <Field label={t("admin.region")}><select className="input" value={np.region} onChange={(e) => setNp({ ...np, region: e.target.value })}>{regions.data?.regions.map((r) => <option key={r.code} value={r.code}>{r.name}</option>)}</select></Field>
            <Field label={t("admin.providerPhone")}><input className="input" value={np.phone} onChange={(e) => setNp({ ...np, phone: e.target.value })} /></Field>
            <Field label={t("admin.providerLangs")}><select className="input" value={np.lang} onChange={(e) => setNp({ ...np, lang: e.target.value as Lang })}>{(["en", "ta", "bn", "te"] as const).map((l) => <option key={l} value={l}>{t(`lang.${l}`)}</option>)}</select></Field>
            <Field label={t("admin.providerServices")}><input className="input" value={np.services} onChange={(e) => setNp({ ...np, services: e.target.value })} /></Field>
            <Field label={t("admin.providerMinStage")}><input className="input" type="number" min={1} max={5} value={np.min_stage} onChange={(e) => setNp({ ...np, min_stage: e.target.value })} /></Field>
            <button className="btn-primary sm:col-span-2 lg:col-span-4" disabled={addProvider.isPending} data-testid="prov-add">{t("admin.providerAdd")}</button>
          </form>
          <div className="overflow-x-auto"><table className="w-full min-w-[520px] text-left text-sm"><tbody>
            {(providers.data?.providers ?? []).map((p) => <tr key={p.id} className="border-t border-line"><td className="py-2 font-semibold">{p.name}</td><td>{p.city}</td><td>{p.kind}</td><td>{p.is_demo ? <Chip tone="warn">{t("admin.providerDemo")}</Chip> : <Chip tone="ok">verified</Chip>}</td><td className="text-right"><button className="btn-ghost !min-h-[32px] text-danger" onClick={() => removeProvider.mutate(p.id)}>{t("admin.providerDelete")}</button></td></tr>)}
          </tbody></table></div>
        </Card>
      </div>
    </>
  );
}
