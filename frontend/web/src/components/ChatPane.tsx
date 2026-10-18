import { useQuery } from "@tanstack/react-query";
import { Check, CheckCheck, FileText, HeartPulse, Paperclip, Pill, Send, X } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import { api, connectThread, type AttachmentInput, type Message, type ServerEvent, type Thread } from "@/lib/api";
import { cn, fmtDate, fmtNumber, fmtTime, stageColor, uid } from "@/lib/utils";
import { useSession } from "@/store/session";
import { Tx } from "@/lib/translate";
import { MiniKidney } from "./LivingKidney";
import { Chip, Modal, Spinner, useNotify } from "./ui";

type Conn = ReturnType<typeof connectThread>;

function AttachmentCard({ m, role }: { m: Message; role: string }) {
  const { t, i18n } = useTranslation();
  const a = m.attachment;
  if (!a) return null;
  if (a.type === "kidney_snapshot") {
    const s = a.state;
    return (
      <div className="mt-2 flex items-center gap-3 rounded-xl bg-white/70 p-2 text-ink">
        <MiniKidney state={s} size={34} />
        <div><p className="text-xs font-bold uppercase text-muted">{t("chat.sharedKidney")}</p>
          {s?.has_data ? <p className="text-sm font-semibold">{t(`gStage.${s.g_stage}`)} · {t(`stages.${s.stage_name}`)} · eGFR {fmtNumber(s.egfr, i18n.language)}</p> : <p className="text-sm">{t("kidney.noData")}</p>}</div>
      </div>
    );
  }
  if (a.type === "lab") {
    const l = a.lab;
    return (
      <div className="mt-2 rounded-xl bg-white/70 p-2 text-ink"><p className="text-xs font-bold uppercase text-muted">{t("chat.sharedLab")} · {fmtDate(l.taken_on, i18n.language)}</p>
        <p className="text-sm">eGFR <b>{fmtNumber(l.egfr, i18n.language)}</b> {l.g_stage && <span className="chip ml-1 text-white" style={{ background: stageColor(l.g_stage) }}>{l.g_stage}</span>} · Cr {fmtNumber(l.scr, i18n.language)} · K {fmtNumber(l.potassium, i18n.language)} · BP {fmtNumber(l.sbp, i18n.language)}</p></div>
    );
  }
  return (
    <Link to={role === "doctor" ? `/doctor/rx/${a.rx_id}` : `/rx?open=${a.rx_id}`} className="mt-2 flex items-center gap-2 rounded-xl bg-white/70 p-2 text-ink">
      <Pill className="h-5 w-5 text-accent" /><span className="text-sm font-semibold">{t("chat.sharedRx", { id: a.rx_id })}</span><Chip tone={a.status === "signed" ? "ok" : "slate"}>{t(`rx.status.${a.status}`)}</Chip>
    </Link>
  );
}

export function ChatPane({ thread, initialAttachment, onClosed, onEvent }: { thread: Thread; initialAttachment?: AttachmentInput | null; onClosed?: () => void; onEvent?: (ev: ServerEvent) => void }) {
  const { t, i18n } = useTranslation();
  const user = useSession((s) => s.user)!;
  const notify = useNotify();
  const [messages, setMessages] = useState<Message[]>([]);
  const [loading, setLoading] = useState(true);
  const [more, setMore] = useState(true);
  const [status, setStatus] = useState<"connecting" | "open" | "closed">("connecting");
  const [online, setOnline] = useState<Set<number>>(new Set());
  const [typing, setTyping] = useState<Record<number, number>>({});
  const [readBy, setReadBy] = useState<Record<number, number>>({});
  const [text, setText] = useState("");
  const [pending, setPending] = useState<AttachmentInput | null>(initialAttachment ?? null);
  const [picker, setPicker] = useState<"lab" | "rx" | null>(null);
  const [menu, setMenu] = useState(false);
  const conn = useRef<Conn | null>(null);
  const bottom = useRef<HTMLDivElement>(null);
  const lastTyping = useRef(0);
  const names = useMemo(() => Object.fromEntries(thread.members.map((m) => [m.id, m.name])), [thread.members]);
  const isRoom = thread.kind === "room";

  const markRead = useCallback((lastId: number) => {
    if (document.hidden || lastId <= 0) return;
    if (conn.current && status === "open") conn.current.read(lastId); else api.markThreadRead(thread.id, lastId).catch(() => {});
  }, [thread.id, status]);

  // history
  useEffect(() => {
    let alive = true;
    setLoading(true); setMessages([]);
    api.messages(thread.id).then((rows) => {
      if (!alive) return;
      setMessages(rows); setMore(rows.length >= 50); setLoading(false);
      const last = rows[rows.length - 1];
      if (last) api.markThreadRead(thread.id, last.id).catch(() => {});
    }).catch((e) => { setLoading(false); notify.error(e); });
    return () => { alive = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [thread.id]);

  // live connection
  useEffect(() => {
    const c = connectThread(thread.id, (ev) => {
      onEvent?.(ev);
      switch (ev.type) {
        case "ready": setOnline(new Set(ev.online)); break;
        case "message":
          setMessages((prev) => {
            const m = ev.message;
            if (prev.some((x) => x.id === m.id)) return prev;
            const i = m.client_id ? prev.findIndex((x) => x.client_id === m.client_id && x.id < 0) : -1;
            if (i >= 0) { const copy = [...prev]; copy[i] = m; return copy; }
            return [...prev, m];
          });
          if (ev.message.sender_id !== user.id) { c.read(ev.message.id); setTyping((p) => { const n = { ...p }; delete n[ev.message.sender_id ?? -1]; return n; }); }
          break;
        case "typing": setTyping((p) => ({ ...p, [ev.user_id]: Date.now() })); break;
        case "read": setReadBy((p) => ({ ...p, [ev.user_id]: Math.max(p[ev.user_id] ?? 0, ev.up_to) })); break;
        case "presence": setOnline((p) => { const n = new Set(p); if (ev.online === false) n.delete(ev.user_id); else n.add(ev.user_id); return n; }); break;
        case "error": notify.errorText(ev.detail); break;
        case "closed": notify.info(t("room.closed")); onClosed?.(); break;
        default: break;
      }
    }, setStatus);
    conn.current = c;
    return () => { c.close(); conn.current = null; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [thread.id]);

  // typing indicator expiry
  useEffect(() => { const id = setInterval(() => setTyping((p) => Object.fromEntries(Object.entries(p).filter(([, ts]) => Date.now() - ts < 3000))), 1000); return () => clearInterval(id); }, []);
  useEffect(() => { bottom.current?.scrollIntoView({ behavior: "smooth" }); }, [messages.length]);
  useEffect(() => { const last = messages[messages.length - 1]; if (last && last.sender_id !== user.id && last.id > 0) markRead(last.id); }, [messages, markRead, user.id]);

  const loadOlder = async () => {
    const first = messages.find((m) => m.id > 0);
    if (!first) return;
    const rows = await api.messages(thread.id, first.id);
    setMessages((p) => [...rows, ...p]); setMore(rows.length >= 50);
  };

  const send = async () => {
    const body = text.trim();
    if (!body && !pending) return;
    if (body.length > 2000) { notify.errorText(t("chat.tooLong")); return; }
    const client_id = uid();
    const optimistic: Message = { id: -Date.now(), thread_id: thread.id, sender_id: user.id, sender_name: user.name, kind: pending ? "attachment" : "text", body, attachment: null, created_at: new Date().toISOString(), client_id };
    setMessages((p) => [...p, optimistic]);
    setText(""); const att = pending; setPending(null);
    if (conn.current && status === "open") { conn.current.sendMessage(body, att ?? undefined, client_id); return; }
    try {
      const m = await api.sendMessage(thread.id, body, att ?? undefined);
      setMessages((p) => p.map((x) => (x.client_id === client_id ? m : x)));
    } catch (e) { setMessages((p) => p.filter((x) => x.client_id !== client_id)); notify.error(e); }
  };

  const others = thread.members.filter((m) => m.id !== user.id);
  const typingNames = Object.keys(typing).map((id) => names[Number(id)]).filter(Boolean);
  const maxReadByOthers = others.length ? Math.min(...others.map((o) => readBy[o.id] ?? 0)) : 0;
  const canShareKidney = user.role === "patient" || user.role === "caregiver";

  return (
    <div className="flex h-full min-h-[420px] flex-col overflow-hidden rounded-xl2 border border-line bg-white" data-testid="chat-pane">
      <div className="flex items-center gap-3 border-b border-line px-4 py-3">
        <div className="min-w-0 flex-1"><p className="truncate font-bold">{thread.title}</p>
          <p className="truncate text-xs text-muted">{others.map((o) => `${o.name}${online.has(o.id) ? " ●" : ""}`).join(", ")}</p></div>
        {others.some((o) => online.has(o.id)) ? <Chip tone="ok">{t("chat.online")}</Chip> : <Chip>{t("chat.offline")}</Chip>}
        {status !== "open" && <Chip tone="warn"><Spinner className="h-3 w-3" />{t("chat.reconnecting")}</Chip>}
      </div>
      <div className="flex-1 space-y-2 overflow-y-auto bg-slate-50 px-3 py-4" aria-live="polite">
        {loading && <div className="grid place-items-center py-6"><Spinner /></div>}
        {more && !loading && messages.length >= 50 && <button className="btn-ghost mx-auto block text-sm" onClick={loadOlder}>{t("app.learnMore")}</button>}
        {!loading && messages.length === 0 && <p className="py-10 text-center text-muted">{t("chat.placeholder")}</p>}
        {messages.map((m) => {
          if (m.kind === "system") return <p key={m.id} className="text-center text-xs text-muted"><Tx text={m.body} /></p>;
          const mine = m.sender_id === user.id;
          return (
            <div key={m.id} className={cn("flex", mine ? "justify-end" : "justify-start")} data-testid="msg">
              <div className={cn("max-w-[85%] rounded-2xl px-3 py-2 shadow-soft", mine ? "bg-accent text-white" : "bg-white text-ink border border-line", m.id < 0 && "opacity-70")}>
                {!mine && isRoom && <p className="text-xs font-bold opacity-80">{m.sender_name}</p>}
                {m.body && <Tx as="p" className="whitespace-pre-wrap break-words" text={m.body} />}
                <AttachmentCard m={m} role={user.role} />
                <p className={cn("mt-1 flex items-center justify-end gap-1 text-[11px]", mine ? "text-white/80" : "text-muted")}>
                  {fmtTime(m.created_at, i18n.language)}
                  {mine && m.id > 0 && (m.id <= maxReadByOthers ? <CheckCheck className="h-3.5 w-3.5" aria-label={t("chat.read")} /> : <Check className="h-3.5 w-3.5" />)}
                </p>
              </div>
            </div>
          );
        })}
        {typingNames.length > 0 && <p className="text-xs italic text-muted">{typingNames.join(", ")} {t("chat.typing")}</p>}
        <div ref={bottom} />
      </div>
      {pending && (
        <div className="flex items-center gap-2 border-t border-line bg-accent-soft px-3 py-2 text-sm">
          <Paperclip className="h-4 w-4" /><span className="flex-1 font-medium">{pending.type === "kidney_snapshot" ? t("chat.shareKidney") : pending.type === "lab" ? t("chat.shareLab") : t("chat.sharedRx", { id: pending.id })}</span>
          <button onClick={() => setPending(null)} aria-label={t("app.cancel")}><X className="h-4 w-4" /></button>
        </div>
      )}
      <div className="relative flex items-end gap-2 border-t border-line p-3">
        <div className="relative">
          <button className="btn-ghost !px-3" onClick={() => setMenu(!menu)} aria-label={t("chat.attach")} data-testid="attach"><Paperclip className="h-5 w-5" /></button>
          {menu && (
            <div className="card absolute bottom-14 left-0 z-20 w-52 p-1 shadow-lift">
              {canShareKidney && <button className="flex min-h-[44px] w-full items-center gap-2 rounded-xl px-3 hover:bg-slate-50" onClick={() => { setPending({ type: "kidney_snapshot" }); setMenu(false); }} data-testid="attach-kidney"><HeartPulse className="h-4 w-4" />{t("chat.shareKidney")}</button>}
              {canShareKidney && <button className="flex min-h-[44px] w-full items-center gap-2 rounded-xl px-3 hover:bg-slate-50" onClick={() => { setPicker("lab"); setMenu(false); }}><FileText className="h-4 w-4" />{t("chat.shareLab")}</button>}
              <button className="flex min-h-[44px] w-full items-center gap-2 rounded-xl px-3 hover:bg-slate-50" onClick={() => { setPicker("rx"); setMenu(false); }}><Pill className="h-4 w-4" />{t("rx.title")}</button>
            </div>
          )}
        </div>
        <textarea data-testid="chat-input" rows={1} className="input max-h-32 min-h-[44px] flex-1 resize-none" placeholder={t("chat.placeholder")} value={text} maxLength={2100}
          onChange={(e) => { setText(e.target.value); if (conn.current && Date.now() - lastTyping.current > 2000) { lastTyping.current = Date.now(); conn.current.typing(); } }}
          onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); void send(); } }} />
        <button className="btn-primary !px-4" onClick={() => void send()} aria-label={t("chat.send")} data-testid="chat-send"><Send className="h-5 w-5" /></button>
      </div>
      <Picker kind={picker} onClose={() => setPicker(null)} onPick={(a) => { setPending(a); setPicker(null); }} />
    </div>
  );
}

function Picker({ kind, onClose, onPick }: { kind: "lab" | "rx" | null; onClose: () => void; onPick: (a: AttachmentInput) => void }) {
  const { t, i18n } = useTranslation();
  const labs = useQuery({ queryKey: ["labs"], queryFn: () => api.labs(), enabled: kind === "lab" });
  const rx = useQuery({ queryKey: ["rx", "list"], queryFn: () => api.rxList(), enabled: kind === "rx" });
  return (
    <Modal open={kind !== null} onClose={onClose} title={kind === "lab" ? t("chat.shareLab") : t("rx.title")}>
      <ul className="space-y-2">
        {kind === "lab" && (labs.data ?? []).slice().reverse().map((l) => (
          <li key={l.id}><button className="w-full rounded-xl border border-line p-3 text-left hover:bg-slate-50" onClick={() => onPick({ type: "lab", id: l.id })}>{fmtDate(l.taken_on, i18n.language)} · eGFR {fmtNumber(l.egfr, i18n.language)}</button></li>
        ))}
        {kind === "rx" && (rx.data ?? []).map((r) => (
          <li key={r.id}><button className="w-full rounded-xl border border-line p-3 text-left hover:bg-slate-50" onClick={() => onPick({ type: "prescription", id: r.id })}>#{r.id} · {t(`rx.status.${r.status}`)}</button></li>
        ))}
        {((kind === "lab" && (labs.data ?? []).length === 0) || (kind === "rx" && (rx.data ?? []).length === 0)) && <li className="text-center text-muted">{t("app.noData")}</li>}
      </ul>
    </Modal>
  );
}
