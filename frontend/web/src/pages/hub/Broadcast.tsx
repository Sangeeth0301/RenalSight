import { useMutation } from "@tanstack/react-query";
import { Check, Copy, MessageCircle, Send, Trash2, UserPlus, Users } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { Card, PageHeader, Segmented, Spinner, useNotify } from "@/components/ui";
import { api, type Lang } from "@/lib/api";
import { loadContacts, parseContacts, saveContacts, smsLink, tgLink, waLink, type Contact } from "@/lib/share";
import { cn, todayISO } from "@/lib/utils";
import { useSession } from "@/store/session";

interface Tpl { key: string; title: string; body: string; needs?: ("date" | "place")[] }
const DOCTOR_TPL: Tpl[] = [
  { key: "appt", title: "Appointment reminder", needs: ["date"], body: "Hello {name}, this is a reminder from {sender}'s clinic about your kidney check-up on {date}. Please bring your latest reports and take your medicines as prescribed. Reply here if you need to change the time." },
  { key: "lab", title: "Lab tests due", body: "Hello {name}, it is time for your kidney blood and urine tests (creatinine and urine protein). Please get them done this week and share the report with us. - {sender}" },
  { key: "tip", title: "Kidney care tip", body: "Hello {name}, a quick kidney tip from {sender}: eat less salt, drink fluids only as advised, avoid pain-killers like ibuprofen or diclofenac, and check your blood pressure regularly." },
  { key: "camp", title: "Screening camp invite", needs: ["date", "place"], body: "Free kidney screening camp at {place} on {date}. A simple blood and urine test can find kidney disease early. Please come, and share this message with your family and friends. - {sender}" },
];
const PATIENT_TPL: Tpl[] = [
  { key: "update", title: "Update my family", body: "Dear {name}, a quick update on my kidney health: I am following my doctor's plan and tracking my reports in RenalSight. Please remind me about medicines and low-salt food. Thank you for your support. - {sender}" },
  { key: "visit", title: "Ask someone to come with me", needs: ["date"], body: "Dear {name}, I would be grateful if you could come with me to my doctor visit on {date}. Having you there means a lot. - {sender}" },
  { key: "water", title: "Reminder to a family helper", body: "Dear {name}, please help me remember: take medicines after food, low salt, only the water my doctor allowed, and no pain-killers without asking. Thank you. - {sender}" },
];
const LANGS: { value: Lang; label: string }[] = [{ value: "en", label: "English" }, { value: "ta", label: "தமிழ்" }, { value: "bn", label: "বাংলা" }, { value: "te", label: "తెలుగు" }];

export default function Broadcast() {
  const notify = useNotify();
  const user = useSession((s) => s.user)!;
  const isDoc = user.role === "doctor";
  const tpls = isDoc ? DOCTOR_TPL : PATIENT_TPL;
  const sender = isDoc ? user.name : user.name.split(" ")[0];
  const [tpl, setTpl] = useState(tpls[0].key);
  const [date, setDate] = useState(todayISO());
  const [place, setPlace] = useState("");
  const [language, setLanguage] = useState<Lang>("en");
  const [mode, setMode] = useState<"people" | "group">("people");
  const [text, setText] = useState("");
  const [aiNote, setAiNote] = useState("");
  const [contacts, setContacts] = useState<Contact[]>(() => loadContacts());
  const [raw, setRaw] = useState("");
  const [copied, setCopied] = useState(false);
  const cur = tpls.find((x) => x.key === tpl)!;

  const base = useMemo(() => cur.body.split("{sender}").join(sender).split("{date}").join(date).split("{place}").join(place || "our clinic"), [cur, sender, date, place]);
  const tr = useMutation({
    mutationFn: async () => {
      if (language === "en") return { text: base, ok: true };
      const r = await api.translate([base], language);
      return { text: r.translated[0] ? r.translations[0] : base, ok: r.translated[0] };
    },
    onSuccess: (r) => { setText(r.text); setAiNote(language !== "en" && !r.ok ? "AI translation is not available right now, so the English text is shown." : ""); },
    onError: (e) => { setText(base); notify.error(e); },
  });
  useEffect(() => { const h = setTimeout(() => tr.mutate(), 350); return () => clearTimeout(h); /* eslint-disable-next-line react-hooks/exhaustive-deps */ }, [base, language]);

  const persist = (c: Contact[]) => { setContacts(c); saveContacts(c); };
  const personal = (c: Contact) => text.split("{name}").join(c.name.split(" ")[0]);
  const groupText = text.split("{name}").join("everyone");
  const importPatients = async () => {
    try {
      const ps = await api.doctorPatients();
      const have = new Set(contacts.map((c) => c.name));
      persist([...contacts, ...ps.filter((p) => !have.has(p.name)).map((p) => ({ id: `p${p.id}`, name: p.name, phone: "" }))]);
      notify.ok(`${ps.length} patients added. Add their WhatsApp numbers to send.`);
    } catch (e) { notify.error(e); }
  };
  const copy = async () => { try { await navigator.clipboard.writeText(mode === "group" ? groupText : text); setCopied(true); setTimeout(() => setCopied(false), 1500); } catch { notify.errorText("Copy failed"); } };
  const ready = contacts.filter((c) => c.phone.trim());

  return (
    <div className="space-y-5" data-testid="broadcast">
      <PageHeader title="WhatsApp messages" subtitle={isDoc ? "Remind patients, share tips or invite them to a camp. Send to a group in one tap, or to each person with their name filled in." : "Keep your family informed and ask for help. Send to a group in one tap, or to each person with their name filled in."}
        right={!isDoc && <Link to="/hub/request/new" className="btn-soft">Looking for a kidney donor?</Link>} />
      <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.1fr)]">
        <Card className="space-y-4">
          <div><p className="label">1. Choose a message</p>
            <div className="flex flex-wrap gap-2">{tpls.map((x) => <button key={x.key} onClick={() => setTpl(x.key)} data-testid={`tpl-${x.key}`} className={cn("min-h-[40px] rounded-xl border px-3 text-sm font-semibold", tpl === x.key ? "border-transparent bg-accent text-[color:var(--on-accent)]" : "border-line")}>{x.title}</button>)}</div></div>
          {(cur.needs?.includes("date") || cur.needs?.includes("place")) && (
            <div className="grid gap-3 sm:grid-cols-2">
              {cur.needs.includes("date") && <div><label className="label">Date</label><input type="date" className="input" value={date} onChange={(e) => setDate(e.target.value)} /></div>}
              {cur.needs.includes("place") && <div><label className="label">Place</label><input className="input" placeholder="Clinic or hall name" value={place} onChange={(e) => setPlace(e.target.value)} /></div>}
            </div>
          )}
          <div><p className="label">2. Language</p><Segmented value={language} onChange={setLanguage} options={LANGS} /></div>
          <div><p className="label">3. Who gets it?</p>
            <Segmented value={mode} onChange={setMode} options={[{ value: "people", label: <span className="flex items-center gap-1"><UserPlus className="h-4 w-4" />People, one by one</span> }, { value: "group", label: <span className="flex items-center gap-1"><Users className="h-4 w-4" />A WhatsApp group</span> }]} /></div>
        </Card>

        <div className="space-y-4">
          <div className="rounded-2xl p-3" style={{ background: "linear-gradient(160deg, color-mix(in srgb, #22c55e 18%, transparent), transparent)" }}>
            <div className="rounded-2xl rounded-tl-sm bg-[#d9fdd3] p-3 text-[15px] leading-relaxed text-slate-900 shadow-soft dark:bg-[#005c4b] dark:text-white">
              {tr.isPending && !text ? <Spinner /> : <textarea aria-label="message" data-testid="bc-text" rows={7} value={mode === "group" ? groupText : text} onChange={(e) => setText(e.target.value)} className="w-full resize-y border-0 bg-transparent p-0 text-inherit outline-none" />}
            </div>
            {aiNote && <p className="mt-2 text-xs text-muted">{aiNote}</p>}
            {mode === "people" && <p className="mt-2 text-xs text-muted">Each person gets their own first name where you see {"{name}"}.</p>}
          </div>

          {mode === "group" ? (
            <Card>
              <p className="mb-3 text-sm text-muted">WhatsApp opens with the message ready. Pick any group or contact and tap send. Nothing is sent without you.</p>
              <div className="flex flex-wrap gap-2">
                <a className="btn-primary" style={{ background: "#16a34a", color: "#fff" }} href={waLink(groupText)} target="_blank" rel="noreferrer" data-testid="bc-group-send"><MessageCircle className="h-5 w-5" />Open WhatsApp and choose a group</a>
                <a className="btn-outline" href={tgLink(groupText)} target="_blank" rel="noreferrer"><Send className="h-4 w-4" />Telegram</a>
                <a className="btn-outline" href={smsLink(groupText)}>SMS</a>
                <button className="btn-outline" onClick={copy}>{copied ? <Check className="h-4 w-4 text-ok" /> : <Copy className="h-4 w-4" />}{copied ? "Copied" : "Copy"}</button>
              </div>
            </Card>
          ) : (
            <Card>
              <div className="mb-2 flex items-center justify-between gap-2"><p className="font-semibold">People ({contacts.length})</p>{isDoc && <button className="btn-soft !min-h-[36px] text-sm" onClick={() => void importPatients()} data-testid="import-patients">Add my patients</button>}</div>
              <textarea className="input min-h-[70px]" placeholder="Paste one per line: Name, phone" value={raw} onChange={(e) => setRaw(e.target.value)} data-testid="bc-raw" />
              <div className="mt-2 flex items-center justify-between"><p className="text-xs text-muted">Saved only in this browser. Numbers need the country code or a 10-digit Indian number.</p>
                <button className="btn-soft" data-testid="bc-add" onClick={() => { const add = parseContacts(raw); if (!add.length) return notify.errorText("No phone numbers found"); persist([...contacts, ...add]); setRaw(""); }}>Add</button></div>
              {contacts.length > 0 && (
                <ul className="mt-3 max-h-80 space-y-1 overflow-auto" data-testid="bc-list">
                  {contacts.map((c) => (
                    <li key={c.id} className="flex items-center gap-2 rounded-xl px-2 py-1 hover:bg-[var(--surface-2)]">
                      <span className="min-w-0 flex-1 truncate text-sm font-semibold">{c.name}</span>
                      <input className="input !min-h-[36px] !w-36 !py-0 text-sm" inputMode="tel" placeholder="WhatsApp no." value={c.phone} onChange={(e) => persist(contacts.map((x) => x.id === c.id ? { ...x, phone: e.target.value } : x))} />
                      {c.phone.trim() ? <a href={waLink(personal(c), c.phone)} target="_blank" rel="noreferrer" onClick={() => persist(contacts.map((x) => x.id === c.id ? { ...x, sent: true } : x))} className={cn("btn-soft !min-h-[36px] !px-3 text-sm", c.sent && "opacity-60")}>{c.sent ? <Check className="h-4 w-4" /> : <MessageCircle className="h-4 w-4" />}Send</a> : <span className="w-[72px] text-center text-xs text-muted">add no.</span>}
                      <button aria-label="remove" className="text-muted hover:text-danger" onClick={() => persist(contacts.filter((x) => x.id !== c.id))}><Trash2 className="h-4 w-4" /></button>
                    </li>
                  ))}
                </ul>
              )}
              {ready.length > 0 && <p className="mt-2 text-xs text-muted">{ready.length} ready to send. Tap each Send; WhatsApp opens for that person.</p>}
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}
