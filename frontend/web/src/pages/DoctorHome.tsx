import * as Dialog from "@radix-ui/react-dialog";
import { useMutation, useQuery } from "@tanstack/react-query";
import { AlertTriangle, ArrowDown, ArrowUp, Bot, CalendarClock, ClipboardList, Copy, FlaskConical, Megaphone, MessageCircle, Plus, Search, Stethoscope, Users, X } from "lucide-react";
import { useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Bar, BarChart, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis, CartesianGrid, LineChart, Line } from "recharts";
import { HelperChat } from "@/components/HelperChat";
import { MiniKidney } from "@/components/LivingKidney";
import { OutreachCard } from "@/components/OutreachCard";
import { Card, Chip, EmptyState, ErrorState, LoadingBlock, SeverityMeter, useNotify } from "@/components/ui";
import { api, type DoctorPatient } from "@/lib/api";
import { cn, fmtDate, stageColor } from "@/lib/utils";
import { useSession } from "@/store/session";

type SortKey = "severity" | "egfr" | "name" | "age" | "slope" | "last";
const STAGES = ["All", "G1-2", "G3", "G4", "G5"] as const;
const stageGroup = (g?: string | null) => (!g ? "none" : g === "G1" || g === "G2" ? "G1-2" : g.startsWith("G3") ? "G3" : g);
const daysSince = (iso: string | null) => (iso ? Math.floor((Date.now() - new Date(iso).getTime()) / 86400000) : null);

export function Sparkline({ values, color = "var(--accent)", w = 84, h = 26 }: { values: number[]; color?: string; w?: number; h?: number }) {
  if (values.length < 2) return <span className="text-xs text-muted">-</span>;
  const lo = Math.min(...values), hi = Math.max(...values), span = hi - lo || 1;
  const pts = values.map((v, i) => `${(i / (values.length - 1)) * (w - 4) + 2},${h - 3 - ((v - lo) / span) * (h - 6)}`).join(" ");
  return <svg width={w} height={h} aria-hidden><polyline points={pts} fill="none" stroke={color} strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" /><circle cx={pts.split(" ").pop()!.split(",")[0]} cy={pts.split(" ").pop()!.split(",")[1]} r={2.6} fill={color} /></svg>;
}

function Kpi({ icon: Icon, label, value, color, onClick, active }: { icon: typeof Users; label: string; value: number | string; color: string; onClick?: () => void; active?: boolean }) {
  return (
    <button type="button" onClick={onClick} className={cn("card kpi flex items-center gap-3 p-4 text-left transition hover:-translate-y-0.5", active && "ring-2 ring-accent")} style={{ ["--kpi" as string]: color }}>
      <span className="grid h-11 w-11 place-items-center rounded-xl" style={{ background: `color-mix(in srgb, ${color} 14%, transparent)`, color }}><Icon className="h-5 w-5" /></span>
      <span><span className="block text-2xl font-extrabold leading-none">{value}</span><span className="text-xs font-medium text-muted">{label}</span></span>
    </button>
  );
}

function PatientDrawer({ p, onClose }: { p: DoctorPatient | null; onClose: () => void }) {
  const nav = useNavigate();
  const notify = useNotify();
  const q = useQuery({ queryKey: ["doctor", "patient", p?.id], queryFn: () => api.doctorPatient(p!.id), enabled: !!p });
  const open = useMutation({ mutationFn: () => api.openDirect(p!.id), onSuccess: (th) => nav(`/chat/${th.id}`), onError: (e) => notify.error(e) });
  const draft = useMutation({ mutationFn: () => api.rxCreateForPatient(p!.id), onSuccess: (r) => nav(`/doctor/rx/${r.id}`), onError: (e) => notify.error(e) });
  const d = q.data, s = p?.state;
  const chart = (d?.labs ?? []).filter((l) => l.egfr !== null).map((l) => ({ date: l.taken_on.slice(2, 7), egfr: l.egfr }));
  const fc = d?.forecast;
  return (
    <Dialog.Root open={!!p} onOpenChange={(o) => !o && onClose()}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-[90] bg-slate-900/40" />
        <Dialog.Content data-testid="drawer" className="fixed inset-y-0 right-0 z-[95] flex w-[min(96vw,520px)] flex-col overflow-y-auto border-l border-line bg-[var(--card-solid)] p-5 shadow-lift">
          {p && s && (
            <>
              <div className="flex items-start gap-3">
                <div className="grid h-14 w-14 shrink-0 place-items-center rounded-2xl bg-accent-soft"><MiniKidney state={s as any} size={34} /></div>
                <div className="min-w-0 flex-1">
                  <Dialog.Title className="truncate text-xl font-bold">{p.name}</Dialog.Title>
                  <Dialog.Description className="text-sm text-muted">{p.age ?? "-"} y / {p.sex ?? "-"} · {p.email}</Dialog.Description>
                  <div className="mt-2 flex flex-wrap gap-1.5">
                    {s.has_data && <span className="chip text-white" style={{ background: stageColor(s.g_stage) }}>{s.g_stage}</span>}
                    {s.urgent && <Chip tone="danger"><AlertTriangle className="h-3 w-3" />Urgent</Chip>}
                    {p.diabetes && <Chip tone="warn">Diabetes</Chip>}{p.hypertension && <Chip tone="info">Hypertension</Chip>}
                  </div>
                </div>
                <Dialog.Close className="rounded-full p-1.5 text-muted hover:bg-[var(--surface-2)]" aria-label="close"><X className="h-5 w-5" /></Dialog.Close>
              </div>

              {s.has_data ? <div className="mt-4"><SeverityMeter value={s.severity ?? 0} /></div> : <p className="mt-4 text-muted">{s.message ?? "No labs yet"}</p>}

              <div className="mt-4 grid grid-cols-4 gap-2 text-center">
                {([["eGFR", d?.snapshot.egfr], ["ACR", d?.snapshot.acr], ["K+", d?.snapshot.potassium], ["BP", d?.snapshot.sbp], ["HbA1c", d?.snapshot.hba1c], ["Hb", d?.snapshot.hgb], ["Cr", d?.snapshot.scr], ["BUN", d?.snapshot.bun]] as const).map(([k, v]) => (
                  <div key={k} className="rounded-xl bg-[var(--surface-3)] p-2"><p className="text-[11px] text-muted">{k}</p><p className="font-bold">{v ?? "-"}</p></div>
                ))}
              </div>

              <div className="mt-4 rounded-xl border border-line p-3">
                <p className="mb-1 text-sm font-semibold">eGFR trend</p>
                {q.isLoading ? <div className="skeleton h-28" /> : chart.length < 2 ? <p className="text-sm text-muted">Not enough results for a trend.</p> : (
                  <div className="h-32"><ResponsiveContainer><LineChart data={chart} margin={{ top: 6, right: 8, left: -22, bottom: 0 }}><CartesianGrid strokeDasharray="3 3" /><XAxis dataKey="date" tick={{ fontSize: 10 }} /><YAxis domain={[0, "auto"]} tick={{ fontSize: 10 }} /><Tooltip /><Line dataKey="egfr" stroke="var(--accent)" strokeWidth={2.5} dot={{ r: 3 }} /></LineChart></ResponsiveContainer></div>
                )}
                {p.slope_per_year !== null && <p className="mt-1 text-xs text-muted">Change: <b className={p.slope_per_year < -3 ? "text-danger" : ""}>{p.slope_per_year > 0 ? "+" : ""}{p.slope_per_year} mL/min per year</b> · {p.labs_count} results</p>}
              </div>

              {fc && fc.has_data !== false && (
                <div className="mt-3 rounded-xl border border-line p-3">
                  <p className="mb-2 text-sm font-semibold">Years to kidney failure (estimate)</p>
                  <div className="grid grid-cols-3 gap-2 text-center">
                    {([["Fast", fc.years_to_stage5_p10], ["Expected", fc.years_to_stage5_p50], ["Slow", fc.years_to_stage5_p90]] as const).map(([k, v]) => <div key={k} className="rounded-lg bg-[var(--surface-3)] p-2"><p className="text-[11px] text-muted">{k}</p><p className="font-bold">{v === null ? ">30" : Math.round(v * 10) / 10}</p></div>)}
                  </div>
                  <p className="mt-2 text-xs text-muted">Risk of kidney failure: 2y {Math.round(fc.prob_kf_2y * 100)}% · 5y {Math.round(fc.prob_kf_5y * 100)}% · 10y {Math.round(fc.prob_kf_10y * 100)}%</p>
                </div>
              )}

              <div className="mt-auto flex flex-wrap gap-2 pt-5">
                <Link to={`/doctor/patients/${p.id}`} className="btn-primary flex-1" data-testid="open-record"><Stethoscope className="h-4 w-4" />Open full record</Link>
                <button className="btn-outline" onClick={() => open.mutate()} data-testid="message-patient"><MessageCircle className="h-4 w-4" />Message</button>
                <button className="btn-outline" onClick={() => draft.mutate()} disabled={draft.isPending}><Plus className="h-4 w-4" />Draft Rx</button>
              </div>
            </>
          )}
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}

export default function DoctorHome() {
  const user = useSession((s) => s.user)!;
  const notify = useNotify();
  const q = useQuery({ queryKey: ["doctor", "patients"], queryFn: () => api.doctorPatients(), refetchInterval: 30000 });
  const queue = useQuery({ queryKey: ["doctor", "queue", "count"], queryFn: () => api.doctorQueue(), refetchInterval: 30000 });
  const appts = useQuery({ queryKey: ["care-hub", "appointments"], queryFn: () => api.appointments() });
  const [search, setSearch] = useState("");
  const [stage, setStage] = useState<(typeof STAGES)[number]>("All");
  const [urgentOnly, setUrgentOnly] = useState(false);
  const [diabetesOnly, setDiabetesOnly] = useState(false);
  const [overdueOnly, setOverdueOnly] = useState(false);
  const [sort, setSort] = useState<{ key: SortKey; dir: 1 | -1 }>({ key: "severity", dir: -1 });
  const [sel, setSel] = useState<DoctorPatient | null>(null);
  const [copilot, setCopilot] = useState(false);
  const [outreachChat, setOutreachChat] = useState(false);

  const all = q.data ?? [];
  const overdue = (p: DoctorPatient) => { const d = daysSince(p.last_lab); return d === null || d > 180; };
  const stats = useMemo(() => ({
    total: all.length, urgent: all.filter((p) => p.state.urgent).length, advanced: all.filter((p) => ["G4", "G5"].includes(p.state.g_stage ?? "")).length, overdue: all.filter(overdue).length,
    upcoming: (appts.data ?? []).filter((a) => a.status !== "cancelled" && new Date(a.starts_at) > new Date()).length,
  }), [all, appts.data]);
  const dist = useMemo(() => ["G1", "G2", "G3a", "G3b", "G4", "G5"].map((g) => ({ g, n: all.filter((p) => p.state.g_stage === g).length })), [all]);

  const list = useMemo(() => {
    const val = (p: DoctorPatient) => ({ severity: p.state.severity ?? -1, egfr: p.state.egfr ?? 999, name: p.name.toLowerCase(), age: p.age ?? 0, slope: p.slope_per_year ?? 0, last: p.last_lab ? new Date(p.last_lab).getTime() : 0 }[sort.key]);
    return all.filter((p) => p.name.toLowerCase().includes(search.toLowerCase()) && (stage === "All" || stageGroup(p.state.g_stage) === stage) && (!urgentOnly || p.state.urgent) && (!diabetesOnly || p.diabetes) && (!overdueOnly || overdue(p)))
      .sort((a, b) => { const x = val(a), y = val(b); return (x < y ? -1 : x > y ? 1 : 0) * sort.dir; });
  }, [all, search, stage, urgentOnly, diabetesOnly, overdueOnly, sort]);

  const attention = useMemo(() => all.filter((p) => p.state.urgent || (p.slope_per_year ?? 0) < -6).slice(0, 5), [all]);
  const th = (key: SortKey, label: string, cls = "") => (
    <th className={cn("th-sort whitespace-nowrap px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-muted", cls)} onClick={() => setSort((s) => ({ key, dir: s.key === key ? (s.dir === 1 ? -1 : 1) : key === "name" ? 1 : -1 }))}>
      {label}{sort.key === key && (sort.dir === 1 ? <ArrowUp className="ml-1 inline h-3 w-3" /> : <ArrowDown className="ml-1 inline h-3 w-3" />)}
    </th>
  );
  const greeting = new Date().getHours() < 12 ? "Good morning" : new Date().getHours() < 17 ? "Good afternoon" : "Good evening";

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div><p className="text-sm font-medium text-muted">{fmtDate(new Date().toISOString(), "en", { weekday: "long", day: "numeric", month: "long" })}</p>
          <h1 className="text-2xl font-bold sm:text-3xl">{greeting}, {user.name}</h1>
          <p className="text-muted">Your clinic at a glance. Select any patient for details.</p></div>
        <div className="flex flex-wrap items-center gap-2">
          <button className="btn-primary" onClick={() => setCopilot(true)} data-testid="open-copilot"><Bot className="h-4 w-4" />Copilot</button>
          <button className="btn-outline" onClick={() => setOutreachChat(true)} data-testid="open-outreach"><Megaphone className="h-4 w-4" />Outreach</button>
          <div className="card flex items-center gap-2 !p-2 !pl-3"><div><p className="text-[10px] font-semibold uppercase text-muted">Patient link code</p><p className="text-lg font-extrabold leading-none tracking-[0.25em]" data-testid="doctor-code-display">{user.doctor_code}</p></div>
            <button className="btn-ghost !px-2" aria-label="copy" onClick={() => { void navigator.clipboard?.writeText(user.doctor_code ?? ""); notify.ok(user.doctor_code ?? ""); }}><Copy className="h-4 w-4" /></button></div>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-5">
        <Kpi icon={Users} label="My patients" value={stats.total} color="#1d6fe0" onClick={() => { setStage("All"); setUrgentOnly(false); setOverdueOnly(false); }} />
        <Kpi icon={AlertTriangle} label="Urgent" value={stats.urgent} color="#e11d48" active={urgentOnly} onClick={() => setUrgentOnly((v) => !v)} />
        <Kpi icon={FlaskConical} label="Labs overdue (6 mo+)" value={stats.overdue} color="#d97706" active={overdueOnly} onClick={() => setOverdueOnly((v) => !v)} />
        <Link to="/doctor/queue" className="contents"><Kpi icon={ClipboardList} label="Rx to review" value={queue.data?.length ?? 0} color="#7c3aed" /></Link>
        <Link to="/doctor/schedule" className="contents"><Kpi icon={CalendarClock} label="Upcoming visits" value={stats.upcoming} color="#0891b2" /></Link>
      </div>

      <div className="grid gap-4 lg:grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)]">
        <Card>
          <p className="mb-2 font-semibold">Patients by kidney stage</p>
          <div className="h-44"><ResponsiveContainer><BarChart data={dist} margin={{ top: 6, right: 8, left: -18, bottom: 0 }}><CartesianGrid strokeDasharray="3 3" vertical={false} /><XAxis dataKey="g" /><YAxis allowDecimals={false} /><Tooltip cursor={{ fill: "rgba(100,140,200,.08)" }} /><Bar dataKey="n" name="Patients" radius={[6, 6, 0, 0]} onClick={(d: any) => setStage(stageGroup(d.g) as any)}>{dist.map((d) => <Cell key={d.g} fill={stageColor(d.g)} />)}</Bar></BarChart></ResponsiveContainer></div>
        </Card>
        <Card>
          <p className="mb-2 flex items-center gap-2 font-semibold"><AlertTriangle className="h-4 w-4 text-danger" />Needs attention</p>
          {attention.length === 0 ? <p className="text-sm text-muted">Nobody is flagged right now.</p> : (
            <ul className="space-y-1.5">{attention.map((p) => (
              <li key={p.id}><button className="flex w-full items-center gap-3 rounded-xl px-2 py-1.5 text-left hover:bg-[var(--surface-2)]" onClick={() => setSel(p)}>
                <span className="chip text-white" style={{ background: stageColor(p.state.g_stage) }}>{p.state.g_stage ?? "?"}</span>
                <span className="min-w-0 flex-1 truncate font-medium">{p.name}</span>
                <span className="text-xs text-muted">{p.state.urgent ? "urgent values" : `${p.slope_per_year} /yr`}</span></button></li>
            ))}</ul>
          )}
        </Card>
      </div>

      <Card className="!p-0">
        <div className="flex flex-wrap items-center gap-3 border-b border-line p-3">
          <div className="relative min-w-[200px] flex-1"><Search className="absolute left-3 top-3 h-5 w-5 text-muted" /><input className="input !pl-10" placeholder="Search patients by name" value={search} onChange={(e) => setSearch(e.target.value)} data-testid="patient-search" /></div>
          <div className="flex flex-wrap gap-1">{STAGES.map((s) => <button key={s} onClick={() => setStage(s)} className={cn("min-h-[36px] rounded-lg px-3 text-sm font-semibold", stage === s ? "bg-accent text-[color:var(--on-accent)]" : "text-muted hover:bg-[var(--surface-2)]")}>{s}</button>)}</div>
          <label className="flex min-h-[36px] items-center gap-2 text-sm"><input type="checkbox" className="h-4 w-4 accent-[var(--accent)]" checked={urgentOnly} onChange={(e) => setUrgentOnly(e.target.checked)} />Urgent</label>
          <label className="flex min-h-[36px] items-center gap-2 text-sm"><input type="checkbox" className="h-4 w-4 accent-[var(--accent)]" checked={diabetesOnly} onChange={(e) => setDiabetesOnly(e.target.checked)} />Diabetes</label>
          <span className="text-sm text-muted">{list.length} shown</span>
        </div>
        {q.isLoading ? <div className="p-4"><LoadingBlock /></div> : q.error ? <div className="p-4"><ErrorState error={q.error} onRetry={() => q.refetch()} /></div> : all.length === 0 ? <div className="p-4"><EmptyState title="No linked patients yet" body="Share your patient link code so patients can connect to you." /></div> : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[780px] text-sm" data-testid="patient-list">
              <thead className="border-b border-line bg-[var(--surface-3)]"><tr>{th("name", "Patient")}{th("severity", "Stage")}{th("egfr", "eGFR")}<th className="px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-muted">Trend</th>{th("slope", "Change /yr")}<th className="px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-muted">Albuminuria</th>{th("last", "Last lab")}<th className="w-28 px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-muted">Severity</th></tr></thead>
              <tbody>
                {list.map((p) => {
                  const s = p.state; const od = overdue(p);
                  return (
                    <tr key={p.id} data-testid="patient-card" tabIndex={0} onClick={() => setSel(p)} onKeyDown={(e) => e.key === "Enter" && setSel(p)} className="cursor-pointer border-b border-line transition last:border-0 hover:bg-[var(--surface-2)]">
                      <td className="px-3 py-2.5"><div className="flex items-center gap-3"><MiniKidney state={s as any} size={26} /><div><p className="font-semibold">{p.name}{s.urgent && <span className="chip ml-2 bg-rose-100 text-rose-800">Urgent</span>}</p><p className="text-xs text-muted">{p.age ?? "-"} / {p.sex ?? "-"}{p.diabetes ? " · DM" : ""}{p.hypertension ? " · HTN" : ""}</p></div></div></td>
                      <td className="px-3 py-2.5">{s.has_data ? <span className="chip text-white" style={{ background: stageColor(s.g_stage) }}>{s.g_stage}</span> : <span className="text-xs text-muted">No labs</span>}</td>
                      <td className="px-3 py-2.5 font-semibold">{s.egfr ?? "-"}</td>
                      <td className="px-3 py-2.5"><Sparkline values={p.trend} color={stageColor(s.g_stage)} /></td>
                      <td className={cn("px-3 py-2.5 font-medium", (p.slope_per_year ?? 0) < -3 ? "text-danger" : "")}>{p.slope_per_year === null ? "-" : `${p.slope_per_year > 0 ? "+" : ""}${p.slope_per_year}`}</td>
                      <td className="px-3 py-2.5">{s.a_category ?? "-"}</td>
                      <td className={cn("whitespace-nowrap px-3 py-2.5", od && "font-medium text-warn")}>{p.last_lab ? fmtDate(p.last_lab, "en", { day: "numeric", month: "short", year: "2-digit" }) : "none"}{od && p.last_lab && " ⚠"}</td>
                      <td className="px-3 py-2.5">{s.has_data ? <SeverityMeter value={s.severity ?? 0} /> : null}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
            {list.length === 0 && <p className="p-6 text-center text-muted">No patient matches these filters.</p>}
          </div>
        )}
      </Card>

      <OutreachCard />
      <PatientDrawer p={sel} onClose={() => setSel(null)} />
      <HelperChat open={copilot} onClose={() => setCopilot(false)} title="Doctor Copilot" hint="Ask about your patients: who is worst, who is overdue, draft a message." placeholder="e.g. Who needs attention today?" send={(m, l) => api.copilotChat(m, l)} testid="copilot" />
      <HelperChat open={outreachChat} onClose={() => setOutreachChat(false)} title="Outreach assistant" hint="Plan screening camps and find overdue patients." placeholder="e.g. Plan a camp for Tamil Nadu" send={(m, l) => api.outreachChat(m, l)} testid="outreach-chat" />
    </div>
  );
}
