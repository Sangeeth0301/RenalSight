import { useMutation, useQuery } from "@tanstack/react-query";
import { Check, MessageCircle, Send } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";
import { useSession } from "@/store/session";
import { Modal, useNotify } from "./ui";

// Strictly the people the owner chose. The backend refuses any other name.
/** One-click "send this patient's summary on WhatsApp". WhatsApp opens with the message ready; the person taps send. */
export function QuickSend({ open, onClose }: { open: boolean; onClose: () => void }) {
  const notify = useNotify();
  const user = useSession((s) => s.user)!;
  const kidney = useSession((s) => s.kidney);
  const isDoc = user.role === "doctor";
  const allowed = useQuery({ queryKey: ["wa", "allowed"], queryFn: () => api.waAllowed(), enabled: open, staleTime: 600000 });
  const status = useQuery({ queryKey: ["wa", "status"], queryFn: () => api.waStatus(), enabled: open, refetchInterval: (q) => (q.state.data?.linked ? false : 3000) });
  const [picked, setPicked] = useState<Record<string, boolean>>({});
  const [job, setJob] = useState<{ id: string; names: string[] } | null>(null);
  const jobQ = useQuery({ queryKey: ["wa", "job", job?.id], queryFn: () => api.waJob(job!.id), enabled: !!job, refetchInterval: (q) => (q.state.data?.done ? false : 2000) });
  const waiting = !!status.data && !status.data.linked && status.data.login_window_open;
  const qrQ = useQuery({ queryKey: ["wa", "qr"], queryFn: () => api.waQr(), enabled: open && waiting, refetchInterval: 2500 });
  const names = allowed.data?.allowed ?? [];
  const chosen = names.filter((n) => picked[n] !== false);
  const [pid, setPid] = useState<number | null>(null);
  const [consent, setConsent] = useState(!isDoc);
  const [extra, setExtra] = useState("");
  const [bg, setBg] = useState("");
  const [phone, setPhone] = useState("");
  const [demo, setDemo] = useState(true);
  const card = useQuery({ queryKey: ["tx", "idcard"], queryFn: () => api.idCard(), enabled: open && !isDoc });
  // blood group and contact number: from the emergency card if filled in, otherwise a clearly fake demo value (the number can never belong to a real person)
  const demoBg = ["O+", "B+", "A+", "AB+", "O-", "B-", "A-", "AB-"][user.id % 8];
  const demoPhone = `+91 00000 ${String(10000 + ((user.id * 7919) % 90000))}`;
  useEffect(() => {
    if (!card.data) return;
    setBg((v) => v || card.data!.blood_group || demoBg);
    setPhone((v) => v || card.data!.contact_phone || demoPhone);
  }, [card.data]); // eslint-disable-line react-hooks/exhaustive-deps
  const bgIsDemo = !card.data?.blood_group, phoneIsDemo = !card.data?.contact_phone;
  const patients = useQuery({ queryKey: ["doctor", "patients"], queryFn: () => api.doctorPatients(), enabled: open && isDoc });
  const labs = useQuery({ queryKey: ["labs"], queryFn: () => api.labs(), enabled: open && !isDoc });

  const text = useMemo(() => {
    if (isDoc) {
      const p = patients.data?.find((x) => x.id === pid);
      if (!p) return "";
      const s = p.state;
      return [`Help needed for a patient (shared with consent)`, `Name: ${p.name}, ${p.age ?? "-"} y, ${p.sex ?? "-"}${p.diabetes ? ", diabetes" : ""}${p.hypertension ? ", hypertension" : ""}`,
        s.has_data ? `Kidney stage ${s.g_stage}, eGFR ${s.egfr}${s.urgent ? " (URGENT values)" : ""}${p.slope_per_year !== null ? `, change ${p.slope_per_year} per year` : ""}` : "No lab results yet",
        extra && `Note: ${extra}`, `From: ${user.name} (RenalSight)`, "Please contact me if you can help."].filter(Boolean).join("\n");
    }
    const l = labs.data?.[labs.data.length - 1];
    const D = demo ? " (demo)" : "";
    const lines = [`🙏 Kidney help request${demo ? " (RenalSight demo: not a real request)" : ""}`, `Patient: ${user.name}, ${user.age ?? ""}${user.age ? " y, " : ""}${user.sex ?? ""}${user.diabetes ? ", diabetes" : ""}${user.hypertension ? ", high BP" : ""}`.replace(/, $/, "")];
    if (kidney?.has_data) lines.push(`Kidney stage ${kidney.g_stage} (${kidney.stage_name}), eGFR ${kidney.egfr}${kidney.urgent ? ", values need urgent attention" : ""}`);
    if (bg) lines.push(`Blood group: ${bg}${bgIsDemo ? D : ""}`);
    if (l) lines.push(`Latest labs: creatinine ${l.scr ?? "-"}, urine protein ${l.acr ?? "-"}, potassium ${l.potassium ?? "-"}, BP ${l.sbp ?? "-"}`);
    if (extra) lines.push(extra);
    if (phone) lines.push(`Contact: ${phone}${phoneIsDemo ? (demo ? " (demo number)" : "") : ""}`);
    lines.push("Please share with friends and family. Donation is voluntary and never paid for.");
    return lines.filter(Boolean).join("\n");
  }, [isDoc, patients.data, pid, labs.data, kidney, user, extra, bg, phone, demo, bgIsDemo, phoneIsDemo]);

  const link = useMutation({ mutationFn: () => api.waLogin(), onSuccess: (r) => notify.info(r.message), onError: (e) => notify.error(e) });
  const send = useMutation({ mutationFn: () => api.waSend({ text, recipients: chosen.map((name) => ({ name })) }), onSuccess: (r) => setJob({ id: r.job_id, names: r.recipients }), onError: (e) => notify.error(e) });
  const canSend = !!text && consent;
  return (
    <Modal open={open} onClose={onClose} title="Send on WhatsApp" description="Sent through your own WhatsApp Web, only to the people listed. Nothing is sent until you click.">
      <div className="space-y-4" data-testid="quicksend">
        {isDoc && (
          <>
            <select className="input" value={pid ?? ""} onChange={(e) => { setPid(e.target.value ? Number(e.target.value) : null); setConsent(false); }} data-testid="qs-patient">
              <option value="">Choose a patient...</option>
              {(patients.data ?? []).map((p) => <option key={p.id} value={p.id}>{p.name}{p.state.g_stage ? ` (${p.state.g_stage})` : ""}</option>)}
            </select>
            <label className="flex items-start gap-2 rounded-xl border border-amber-300/60 p-3 text-sm"><input type="checkbox" className="mt-1 h-5 w-5 accent-[var(--accent)]" checked={consent} onChange={(e) => setConsent(e.target.checked)} data-testid="qs-consent" />The patient agreed that these details may be shared with these people.</label>
          </>
        )}
        {!isDoc && (
          <div className="grid gap-2 sm:grid-cols-2" data-testid="qs-fields">
            <div><label className="label">Blood group</label><select className="input" value={bg} onChange={(e) => setBg(e.target.value)} data-testid="qs-bg">{["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"].map((g) => <option key={g}>{g}</option>)}</select></div>
            <div><label className="label">Contact number</label><input className="input" inputMode="tel" value={phone} onChange={(e) => setPhone(e.target.value)} data-testid="qs-phone" /></div>
            <label className="flex items-center gap-2 text-sm sm:col-span-2"><input type="checkbox" className="h-5 w-5 accent-[var(--accent)]" checked={demo} onChange={(e) => setDemo(e.target.checked)} data-testid="qs-demo" />Mark the message as a demo (recommended for testing: people will not think it is a real appeal)</label>
          </div>
        )}
        <textarea className="input min-h-[60px]" placeholder="Add a short note (optional)" value={extra} onChange={(e) => setExtra(e.target.value)} />
        <div className="rounded-2xl rounded-tl-sm bg-[#d9fdd3] p-3 text-[14px] leading-relaxed text-slate-900 dark:bg-[#005c4b] dark:text-white" data-testid="qs-preview"><p className="whitespace-pre-wrap">{text || (isDoc ? "Choose a patient to see the message." : "Loading...")}</p></div>

        <div>
          <p className="label">Send to (only these people)</p>
          <ul className="space-y-1.5" data-testid="qs-recipients">
            {names.map((n) => (
              <li key={n} className="flex items-center gap-3 rounded-xl border border-line p-2.5">
                <input type="checkbox" className="h-5 w-5 accent-[var(--accent)]" checked={picked[n] !== false} onChange={(e) => setPicked({ ...picked, [n]: e.target.checked })} aria-label={n} data-testid={`qs-pick-${n.toLowerCase().replace(/[^a-z0-9]+/g, "")}`} />
                <span className="min-w-0 flex-1 font-semibold">{n}</span>
                {jobQ.data?.results.find((x) => x.name === n) ? (jobQ.data.results.find((x) => x.name === n)!.ok ? <span className="chip bg-emerald-100 text-emerald-800"><Check className="h-3 w-3" />Sent</span> : <span className="chip bg-rose-100 text-rose-800" title={jobQ.data.results.find((x) => x.name === n)!.error}>Failed</span>) : job && !jobQ.data?.done && picked[n] !== false ? <span className="text-xs text-muted">sending...</span> : null}
              </li>
            ))}
          </ul>
          {jobQ.data?.results.some((x) => !x.ok) && <p className="mt-2 text-xs text-danger" data-testid="qs-errors">{jobQ.data.results.filter((x) => !x.ok).map((x) => `${x.name}: ${x.error}`).join(" | ")}</p>}
        </div>

        {status.data && !status.data.linked ? (
          <div className="rounded-xl border border-amber-300/60 p-3 text-sm" data-testid="qs-link">
            <p className="mb-2">{status.data.note}</p>
            <button className="btn-soft" onClick={() => link.mutate()} disabled={link.isPending || !status.data.node}><MessageCircle className="h-4 w-4" />Link WhatsApp (one time)</button>
            {waiting && (
              <div className="mt-3 text-center" data-testid="qs-qr">
                {qrQ.data ? <img src={qrQ.data} alt="WhatsApp QR" className="mx-auto w-full max-w-[300px] rounded-xl border border-line" /> : <p className="text-xs text-muted">Getting the QR code...</p>}
                <p className="mt-2 text-xs text-muted">On your phone: WhatsApp &gt; Linked devices &gt; Link a device, then point the camera at this screen. The code refreshes by itself; keep this window open until it says linked.</p>
              </div>
            )}
          </div>
        ) : (
          <button className="btn-primary w-full" style={{ background: "#16a34a", color: "#fff" }} disabled={!canSend || chosen.length === 0 || send.isPending || (!!job && !jobQ.data?.done)} onClick={() => send.mutate()} data-testid="qs-send-now">
            <Send className="h-5 w-5" />{send.isPending || (job && !jobQ.data?.done) ? "Sending..." : `Send now to ${chosen.length} ${chosen.length === 1 ? "person" : "people"}`}
          </button>
        )}
        <p className="text-xs text-muted">Sends through your own WhatsApp Web on this computer, only to the people above. Nothing is sent until you click.</p>
      </div>
    </Modal>
  );
}
