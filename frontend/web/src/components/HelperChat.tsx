import { Tx, TranslateToggle } from "@/lib/translate";
import { useMutation } from "@tanstack/react-query";
import { Bot, Info, Send, X } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import { api, type BuddyReply } from "@/lib/api";
import { currentLang } from "@/i18n";
import { cn } from "@/lib/utils";
import { Spinner, useNotify } from "./ui";

interface Line { role: "user" | "bot"; text: string; tools?: string[]; basic?: boolean }

/** Floating chat used by Doctor Copilot and the Outreach assistant. */
export function HelperChat({ open, onClose, title, hint, placeholder, send, testid }: { open: boolean; onClose: () => void; title: string; hint: string; placeholder: string; send: (m: string, lang: ReturnType<typeof currentLang>) => Promise<BuddyReply>; testid: string }) {
  const { t } = useTranslation();
  const notify = useNotify();
  const [text, setText] = useState("");
  const [log, setLog] = useState<Line[]>([]);
  const m = useMutation({
    mutationFn: (q: string) => send(q, currentLang()),
    onSuccess: (r) => setLog((p) => [...p, { role: "bot", text: r.reply, tools: r.tools_used.filter((x) => x.ok).map((x) => x.tool), basic: r.provider === "rules" }]),
    onError: (e) => notify.error(e),
  });
  const go = () => { const q = text.trim(); if (!q) return; setLog((p) => [...p, { role: "user", text: q }]); setText(""); m.mutate(q); };
  if (!open) return null;
  return (
    <div className="card fixed bottom-4 right-4 z-[60] flex h-[min(72vh,580px)] w-[min(94vw,420px)] flex-col overflow-hidden shadow-lift" data-testid={testid}>
      <div className="flex items-center gap-2 border-b border-line bg-accent-soft px-4 py-3"><Bot className="h-5 w-5 text-accent" /><p className="flex-1 font-bold">{title}</p><TranslateToggle compact /><button onClick={onClose} aria-label="close"><X className="h-5 w-5" /></button></div>
      <div className="flex-1 space-y-2 overflow-y-auto bg-slate-50 p-3">
        {log.length === 0 && <p className="flex gap-2 text-sm text-muted"><Info className="h-4 w-4 shrink-0" />{hint}</p>}
        {log.map((l, i) => (
          <div key={i} className={cn("max-w-[92%] rounded-2xl px-3 py-2 text-sm", l.role === "user" ? "ml-auto bg-accent text-white" : "border border-line bg-white")} data-testid={l.role === "bot" ? `${testid}-reply` : undefined}>
            <Tx as="p" className="whitespace-pre-wrap" text={l.text} />
            {l.basic && <p className="mt-1 text-xs text-muted">{t("app.basicMode")}</p>}
            {l.tools && l.tools.length > 0 && <p className="mt-1 text-[11px] text-muted">{[...new Set(l.tools)].join(", ")}{l.tools.some((x) => x.includes("draft") || x.includes("plan")) && <> · <Link to="/inbox" className="font-semibold text-accent underline">{t("nav.agentInbox")}</Link></>}</p>}
          </div>
        ))}
        {m.isPending && <p className="animate-pulse text-sm text-muted">{t("buddy.thinking")}</p>}
      </div>
      <div className="flex gap-2 border-t border-line p-2">
        <input className="input" data-testid={`${testid}-input`} placeholder={placeholder} value={text} onChange={(e) => setText(e.target.value)} onKeyDown={(e) => e.key === "Enter" && go()} maxLength={1000} />
        <button className="btn-primary !px-3" onClick={go} disabled={m.isPending} aria-label={t("app.send")} data-testid={`${testid}-send`}>{m.isPending ? <Spinner className="text-white" /> : <Send className="h-5 w-5" />}</button>
      </div>
    </div>
  );
}

export { api };
