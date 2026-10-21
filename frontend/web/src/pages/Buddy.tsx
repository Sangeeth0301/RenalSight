import { Tx } from "@/lib/translate";
import { Rich } from "@/components/Rich";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Bot, Mic, MicOff, Send, Trash2, Volume2 } from "lucide-react";
import { useEffect, useRef, useState, type ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import { Chip, Modal, Spinner, useInterval, useNotify } from "@/components/ui";
import { api, type BuddyReply } from "@/lib/api";
import { currentLang, SPEECH_LOCALE } from "@/i18n";
import { cn, tx, uid } from "@/lib/utils";

interface Msg { id: string; role: "user" | "assistant"; content: string; provider?: string | null; tools?: BuddyReply["tools_used"]; doseRemoved?: boolean }

/** very small markdown: **bold** and "- " bullets, rendered as React nodes (never innerHTML). */
const SR: any = typeof window !== "undefined" ? (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition : null;

export default function Buddy() {
  const { t, i18n } = useTranslation();
  const qc = useQueryClient();
  const notify = useNotify();
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [text, setText] = useState("");
  const [listening, setListening] = useState(false);
  const [confirmClear, setConfirmClear] = useState(false);
  const [voiceWarned, setVoiceWarned] = useState(false);
  const bottom = useRef<HTMLDivElement>(null);
  const rec = useRef<any>(null);

  const hist = useQuery({ queryKey: ["buddy", "history"], queryFn: () => api.buddyHistory(30) });
  const status = useQuery({ queryKey: ["buddy", "status"], queryFn: () => api.buddyStatus() });
  useInterval(() => { void status.refetch(); }, 60000);
  useEffect(() => { if (hist.data) setMsgs(hist.data.map((h, i) => ({ id: `h${i}`, role: h.role, content: h.content, provider: h.provider }))); }, [hist.data]);
  useEffect(() => { bottom.current?.scrollIntoView({ behavior: "smooth" }); }, [msgs.length]);

  const send = useMutation({
    mutationFn: (m: string) => api.buddyChat(m, currentLang()),
    onSuccess: (r) => { setMsgs((p) => [...p, { id: uid(), role: "assistant", content: r.reply, provider: r.provider, tools: r.tools_used, doseRemoved: r.dose_removed }]); void qc.invalidateQueries({ queryKey: ["buddy", "status"] }); },
    onError: (e) => notify.error(e),
  });
  const clear = useMutation({ mutationFn: () => api.clearBuddyHistory(), onSuccess: () => { setMsgs([]); setConfirmClear(false); }, onError: (e) => notify.error(e) });

  const submit = (m?: string) => {
    const content = (m ?? text).trim();
    if (!content || send.isPending) return;
    setMsgs((p) => [...p, { id: uid(), role: "user", content }]);
    setText("");
    send.mutate(content);
  };

  const toggleMic = () => {
    if (!SR) { if (!voiceWarned) { notify.errorText(t("buddy.voiceUnavailable")); setVoiceWarned(true); } return; }
    if (listening) { rec.current?.stop(); return; }
    const r = new SR();
    r.lang = SPEECH_LOCALE[currentLang()];
    r.interimResults = false;
    r.onresult = (ev: any) => setText((p) => (p ? p + " " : "") + ev.results[0][0].transcript);
    r.onerror = () => { setListening(false); if (!voiceWarned) { notify.errorText(t("buddy.voiceUnavailable")); setVoiceWarned(true); } };
    r.onend = () => setListening(false);
    rec.current = r; setListening(true); r.start();
  };

  const speak = (s: string) => {
    if (!("speechSynthesis" in window)) { notify.errorText(t("buddy.voiceUnavailable")); return; }
    const u = new SpeechSynthesisUtterance(s);
    u.lang = SPEECH_LOCALE[currentLang()];
    const v = speechSynthesis.getVoices().find((x) => x.lang.toLowerCase().startsWith(u.lang.slice(0, 2).toLowerCase()));
    if (!v && currentLang() !== "en") { notify.errorText(t("buddy.voiceUnavailable")); return; }
    if (v) u.voice = v;
    speechSynthesis.cancel(); speechSynthesis.speak(u);
  };

  const online = status.data?.ai_online;
  const hint = (m: Msg) => {
    if (m.role !== "assistant") return null;
    if (/lab|report|ஆய்வக|ল্যাব|ల్యాబ్/i.test(m.content) && /add|சேர்|যোগ|జోడ/i.test(m.content)) return <Link to="/reports" className="btn-soft mt-2 !min-h-[36px] text-sm">{t("kidney.addLab")}</Link>;
    return null;
  };

  return (
    <div className="flex h-[calc(100vh-7rem)] min-h-[480px] flex-col overflow-hidden rounded-xl2 border border-line bg-white">
      <div className="flex items-center gap-3 border-b border-line px-4 py-3">
        <span className="grid h-11 w-11 place-items-center rounded-full bg-accent-soft text-accent"><Bot className="h-6 w-6" /></span>
        <div className="min-w-0 flex-1"><h1 className="text-xl font-bold">{t("buddy.title")}</h1><p className="truncate text-sm text-muted">{t("buddy.subtitle")}</p></div>
        <Chip tone={online ? "ok" : "warn"}>{online ? "AI" : t("app.basicMode").split(":")[0]}</Chip>
        <button className="btn-ghost !px-3" onClick={() => setConfirmClear(true)} aria-label={t("buddy.clear")} data-testid="clear-chat"><Trash2 className="h-5 w-5" /></button>
      </div>
      {online === false && <p className="border-b border-amber-200 bg-amber-50 px-4 py-2 text-sm text-amber-900" data-testid="basic-banner">{t("app.basicMode")}</p>}
      <div className="flex-1 space-y-3 overflow-y-auto bg-slate-50 px-3 py-4" aria-live="polite" data-testid="buddy-messages">
        {hist.isLoading && <div className="grid place-items-center py-6"><Spinner /></div>}
        {!hist.isLoading && msgs.length === 0 && (
          <div className="mx-auto max-w-md py-10 text-center"><Bot className="mx-auto h-10 w-10 text-accent" />
            <div className="mt-4 flex flex-wrap justify-center gap-2">{(["explain", "eat", "forecast"] as const).map((s) => <button key={s} className="chip bg-white !px-3 !py-2 text-sm shadow-soft hover:bg-accent-soft" onClick={() => submit(t(`buddy.suggestions.${s}`))}>{t(`buddy.suggestions.${s}`)}</button>)}</div></div>
        )}
        {msgs.map((m) => (
          <div key={m.id} className={cn("flex", m.role === "user" ? "justify-end" : "justify-start")}>
            <div className={cn("max-w-[88%] rounded-2xl px-4 py-2.5 shadow-soft", m.role === "user" ? "bg-accent text-white" : "border border-line bg-white")} data-testid={m.role === "assistant" ? "buddy-reply" : "buddy-user"}>
              {m.role === "assistant" ? <Tx text={m.content} as="div" render={(x) => <Rich text={x} />} /> : <Tx as="p" className="whitespace-pre-wrap" text={m.content} />}
              {m.role === "assistant" && (
                <div className="mt-2 flex flex-wrap items-center gap-1.5">
                  {m.tools && m.tools.length > 0 && <span className="chip bg-slate-100 text-slate-600">{tx(t, "buddy.tools", { list: [...new Set(m.tools.map((x) => t(`buddy.toolNames.${x.tool}`, { defaultValue: x.tool })))].join(", ") })}</span>}
                  {m.provider === "rules" && <Chip tone="warn">{t("app.basicMode").split(":")[0]}</Chip>}
                  {m.doseRemoved && <span className="chip bg-amber-100 text-amber-800">{t("buddy.notDoctor")}</span>}
                  <button className="rounded-full p-1.5 text-muted hover:bg-slate-100" onClick={() => speak(m.content)} aria-label={t("buddy.voiceOut")}><Volume2 className="h-4 w-4" /></button>
                </div>
              )}
              {hint(m)}
            </div>
          </div>
        ))}
        {send.isPending && <div className="flex"><div className="rounded-2xl border border-line bg-white px-4 py-3 text-muted"><span className="animate-pulse">{t("buddy.thinking")}</span></div></div>}
        <div ref={bottom} />
      </div>
      <div className="border-t border-line p-3">
        <div className="flex items-end gap-2">
          <button className={cn("btn-ghost !px-3", listening && "bg-rose-100 text-danger")} onClick={toggleMic} aria-label={t("buddy.voiceIn")} data-testid="mic">{listening ? <MicOff className="h-5 w-5" /> : <Mic className="h-5 w-5" />}</button>
          <textarea data-testid="buddy-input" rows={1} className="input max-h-32 min-h-[44px] flex-1 resize-none" placeholder={t("buddy.placeholder")} maxLength={1000} value={text} lang={i18n.language}
            onChange={(e) => setText(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); submit(); } }} />
          <button className="btn-primary !px-4" onClick={() => submit()} disabled={send.isPending} aria-label={t("app.send")} data-testid="buddy-send">{send.isPending ? <Spinner className="text-white" /> : <Send className="h-5 w-5" />}</button>
        </div>
        <p className="mt-2 text-center text-xs text-muted">{t("buddy.notDoctor")}</p>
      </div>
      <Modal open={confirmClear} onClose={() => setConfirmClear(false)} title={t("buddy.clear")}>
        <div className="flex justify-end gap-2"><button className="btn-outline" onClick={() => setConfirmClear(false)}>{t("app.cancel")}</button><button className="btn-danger" onClick={() => clear.mutate()} data-testid="confirm-clear">{t("buddy.clear")}</button></div>
      </Modal>
    </div>
  );
}
