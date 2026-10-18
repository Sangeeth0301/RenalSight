import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { BadgeCheck, Building2, Globe2, Phone } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Card, Chip, EmptyState, ErrorState, Field, LoadingBlock, Modal, PageHeader, Tabs, useDebounced, useNotify } from "@/components/ui";
import { api, type Hospital } from "@/lib/api";
import { useSession } from "@/store/session";

const SHIFTS = ["morning", "afternoon", "evening", "night"];

export default function Hospitals() {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const notify = useNotify();
  const user = useSession((s) => s.user)!;
  const staff = user.role === "doctor" || user.role === "admin";
  const [tab, setTab] = useState<"dir" | "seats">("dir");
  const [q, setQ] = useState("");
  const [tx, setTx] = useState(false);
  const dq = useDebounced(q, 250);
  const dir = useQuery({ queryKey: ["tx", "hospitals", dq, tx], queryFn: () => api.hospitals({ q: dq, transplant: tx ? true : undefined, limit: 40 }) });
  const seats = useQuery({ queryKey: ["tx", "seats", dq], queryFn: () => api.seatBoard(dq), enabled: tab === "seats" });
  const [edit, setEdit] = useState<Hospital | null>(null);
  const [form, setForm] = useState({ shift: "morning", total: 10, free: 0 });
  const save = useMutation({ mutationFn: () => api.setSeats(edit!.id, form), onSuccess: () => { notify.ok("Updated"); setEdit(null); void qc.invalidateQueries({ queryKey: ["tx", "seats"] }); }, onError: (e) => notify.error(e) });

  return (
    <div className="space-y-4">
      <PageHeader title={t("transplant.hospitalsTitle", "Hospitals and dialysis seats")} subtitle={t("transplant.hospitalsSubtitle", "A directory of well-known hospitals in India and abroad. Names only: confirm details on the hospital's official website or by phone.")} />
      <Tabs value={tab} onChange={setTab} tabs={[{ value: "dir", label: t("transplant.directory", "Directory") }, { value: "seats", label: t("transplant.seats", "Dialysis seats") }]} />
      <div className="flex flex-wrap gap-3">
        <input className="input max-w-md flex-1" placeholder={t("transplant.searchHospital", "Search AIIMS, KMCH, Kolkata...") as string} value={q} onChange={(e) => setQ(e.target.value)} data-testid="hospital-search" />
        {tab === "dir" && <label className="flex min-h-[44px] items-center gap-2 text-sm"><input type="checkbox" className="h-5 w-5 accent-[var(--accent)]" checked={tx} onChange={(e) => setTx(e.target.checked)} />{t("transplant.transplantOnly", "Transplant programmes only")}</label>}
      </div>

      {tab === "dir" ? (
        dir.isLoading ? <LoadingBlock /> : dir.error ? <ErrorState error={dir.error} /> : !dir.data?.length ? <EmptyState title={t("transplant.noHospitals", "No hospital found")} /> : (
          <div className="grid gap-3 md:grid-cols-2" data-testid="hospital-list">
            {dir.data.map((h) => (
              <Card key={h.id}>
                <div className="flex items-start gap-3">
                  <div className="grid h-11 w-11 shrink-0 place-items-center rounded-xl bg-accent-soft text-accent">{h.country === "India" ? <Building2 className="h-5 w-5" /> : <Globe2 className="h-5 w-5" />}</div>
                  <div className="min-w-0 flex-1">
                    <p className="font-semibold">{h.name}</p>
                    <p className="text-sm text-muted">{[h.city, h.state, h.country].filter(Boolean).join(", ")}</p>
                    <div className="mt-2 flex flex-wrap gap-2">{h.transplant && <Chip tone="info">{t("transplant.txProgramme", "Transplant programme")}</Chip>}{h.verified ? <Chip tone="ok"><BadgeCheck className="h-3 w-3" />{t("transplant.verified", "Verified")}</Chip> : <Chip tone="slate">{t("transplant.unverified", "Not verified")}</Chip>}{h.phone && <a className="chip bg-accent-soft" href={`tel:${h.phone}`}><Phone className="h-3 w-3" />{h.phone}</a>}</div>
                  </div>
                </div>
              </Card>
            ))}
          </div>
        )
      ) : seats.isLoading ? <LoadingBlock /> : seats.error ? <ErrorState error={seats.error} /> : (
        <>
          <p className="text-sm text-muted">{seats.data?.note}</p>
          <div className="grid gap-3 md:grid-cols-2" data-testid="seat-list">
            {seats.data?.hospitals.map((h) => (
              <Card key={h.id}>
                <div className="flex items-start justify-between gap-2">
                  <div><p className="font-semibold">{h.short_name || h.name}</p><p className="text-sm text-muted">{h.city}</p></div>
                  <span className={`chip ${h.free_total > 0 ? "bg-emerald-100 text-emerald-800" : "bg-rose-100 text-rose-800"}`}>{h.free_total} {t("transplant.freeSeats", "free")}</span>
                </div>
                <div className="mt-3 grid grid-cols-3 gap-2 text-center text-sm">
                  {Object.entries(h.seats).map(([s, v]) => <div key={s} className="rounded-xl border border-line p-2"><p className="capitalize text-muted">{s}</p><p className="font-bold">{v.free}/{v.total}</p></div>)}
                </div>
                {staff && <button className="btn-soft mt-3 !min-h-[36px] text-sm" onClick={() => { setEdit(h); setForm({ shift: "morning", total: 10, free: 0 }); }}>Update seats</button>}
              </Card>
            ))}
          </div>
        </>
      )}

      <Modal open={!!edit} onClose={() => setEdit(null)} title={`Update seats: ${edit?.short_name ?? ""}`}>
        <div className="space-y-3">
          <Field label="Shift"><select className="input" value={form.shift} onChange={(e) => setForm({ ...form, shift: e.target.value })}>{SHIFTS.map((s) => <option key={s}>{s}</option>)}</select></Field>
          <div className="grid grid-cols-2 gap-3">
            <Field label="Total seats"><input className="input" type="number" min={0} value={form.total} onChange={(e) => setForm({ ...form, total: Number(e.target.value) })} /></Field>
            <Field label="Free now"><input className="input" type="number" min={0} value={form.free} onChange={(e) => setForm({ ...form, free: Number(e.target.value) })} /></Field>
          </div>
          <button className="btn-primary w-full" onClick={() => save.mutate()}>Save</button>
        </div>
      </Modal>
    </div>
  );
}
