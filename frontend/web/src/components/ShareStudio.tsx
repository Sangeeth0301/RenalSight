import { useMutation } from "@tanstack/react-query";
import { Check, Copy, Mail, MessageCircle, Printer, Send, Share2, Sparkles, Trash2, UserPlus } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { api, type ComposeInput, type Composed, type Lang, type Tone } from "@/lib/api";
import { loadContacts, mailLink, parseContacts, saveContacts, smsLink, tgLink, waLink, type Contact } from "@/lib/share";
import { cn } from "@/lib/utils";
import { QR } from "./QR";
import { Segmented, Spinner, useNotify } from "./ui";

const LANGS: { value: Lang; label: string }[] = [{ value: "en", label: "English" }, { value: "ta", label: "தமிழ்" }, { value: "bn", label: "বাংলা" }, { value: "te", label: "తెలుగు" }];

/** Writes the appeal, shows it like a chat bubble and opens WhatsApp / Telegram / SMS / e-mail in one click. Nothing is sent automatically. */
export function ShareStudio({ input, requestId, publicUrl, ready }: { input: ComposeInput; requestId?: number; publicUrl?: string; ready: boolean }) {
  const { t, i18n } = useTranslation();
  const notify = useNotify();
  const [language, setLanguage] = useState<Lang>((["en", "ta", "bn", "te"].includes(i18n.language) ? i18n.language : "en") as Lang);
  const [tone, setTone] = useState<Tone>(input.tone ?? "warm");
  const [polish, setPolish] = useState(false);
  const [includePhone, setIncludePhone] = useState(true);
  const [res, setRes] = useState<Composed | null>(null);
  const [text, setText] = useState("");
  const [edited, setEdited] = useState(false);
  const [copied, setCopied] = useState(false);
  const [contacts, setContacts] = useState<Contact[]>(() => loadContacts());
  const [raw, setRaw] = useState("");
  const seq = useRef(0);

  const key = JSON.stringify([input, language, tone, polish, includePhone, requestId, publicUrl]);
  const compose = useMutation({
    mutationFn: () => {
      const link = publicUrl ?? "";
      return requestId
        ? api.composeForRequest(requestId, { tone, language, include_phone: includePhone, polish, link })
        : api.compose({ ...input, tone, language, include_phone: includePhone, polish, link });
    },
    onSuccess: (r) => { setRes(r); setText(r.text); setEdited(false); },
    onError: (e) => notify.error(e),
  });
  useEffect(() => {
    if (!ready) return;
    const id = ++seq.current;
    const h = setTimeout(() => { if (id === seq.current) compose.mutate(); }, 450);
    return () => clearTimeout(h);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key, ready]);

  const persist = (c: Contact[]) => { setContacts(c); saveContacts(c); };
  const links = useMemo(() => ({ wa: waLink(text), tg: tgLink(text), sms: smsLink(text), mail: mailLink(text) }), [text]);
  const copy = async () => { try { await navigator.clipboard.writeText(text); setCopied(true); setTimeout(() => setCopied(false), 1800); } catch { notify.errorText("Copy failed"); } };
  const nativeShare = async () => { try { await navigator.share({ text }); } catch { /* cancelled */ } };
  const canShare = typeof navigator !== "undefined" && "share" in navigator;

  return (
    <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.1fr)]" data-testid="share-studio">
      <div className="space-y-4">
        <div>
          <p className="label">{t("transplant.language", "Message language")}</p>
          <Segmented value={language} onChange={setLanguage} options={LANGS} />
        </div>
        <div>
          <p className="label">{t("transplant.tone", "Tone")}</p>
          <Segmented value={tone} onChange={setTone} options={[{ value: "warm", label: t("transplant.toneWarm", "Warm") }, { value: "formal", label: t("transplant.toneFormal", "Formal") }, { value: "urgent", label: t("transplant.toneUrgent", "Urgent") }]} />
        </div>
        <label className="flex min-h-[44px] cursor-pointer items-center justify-between gap-3 rounded-xl border border-line px-3">
          <span className="text-sm font-medium">{t("transplant.includePhone", "Show my contact number in the message")}</span>
          <input type="checkbox" className="h-5 w-5 accent-[var(--accent)]" checked={includePhone} onChange={(e) => setIncludePhone(e.target.checked)} />
        </label>
        <label className="flex min-h-[44px] cursor-pointer items-center justify-between gap-3 rounded-xl border border-line px-3">
          <span className="flex items-center gap-2 text-sm font-medium"><Sparkles className="h-4 w-4 text-accent" />{t("transplant.polish", "Improve wording with AI")}</span>
          <input type="checkbox" className="h-5 w-5 accent-[var(--accent)]" checked={polish} onChange={(e) => setPolish(e.target.checked)} data-testid="polish" />
        </label>
        {res && polish && <p className="text-xs text-muted">{res.written_by === "ai" ? t("transplant.aiWrote", "Wording improved by AI; all facts were checked.") : t("transplant.aiOffline", "AI is not available right now, so the standard wording is used.")}</p>}
        {res && <p className="text-xs text-muted">{t("transplant.compatLine", "Donors with blood group {{g}} can be tested.", { g: res.compatible_groups.join(", ") })}</p>}
        {res?.tips && <ul className="space-y-1 text-xs text-muted">{res.tips.map((x) => <li key={x}>• {x}</li>)}</ul>}
      </div>

      <div className="space-y-4">
        <div className="rounded-2xl p-3" style={{ background: "linear-gradient(160deg, color-mix(in srgb, #22c55e 18%, transparent), transparent)" }}>
          <div className="relative rounded-2xl rounded-tl-sm bg-[#d9fdd3] p-3 text-[15px] leading-relaxed text-slate-900 shadow-soft dark:bg-[#005c4b] dark:text-white" style={{ maxWidth: "100%" }}>
            {compose.isPending && !res ? <Spinner /> : (
              <textarea aria-label="message" data-testid="share-text" value={text} onChange={(e) => { setText(e.target.value); setEdited(true); }} rows={12}
                className="w-full resize-y border-0 bg-transparent p-0 text-[15px] leading-relaxed text-inherit outline-none" />
            )}
            <p className="mt-1 text-right text-[11px] opacity-60">{text.length} · {edited ? t("transplant.edited", "edited") : t("transplant.draft", "draft")}</p>
          </div>
        </div>
        <div className="flex flex-wrap gap-2">
          <a className={cn("btn-primary flex-1 !bg-[#16a34a] !bg-none sm:flex-none", !text && "pointer-events-none opacity-50")} style={{ background: "#16a34a", color: "#fff" }} href={links.wa} target="_blank" rel="noreferrer" data-testid="wa-send"><MessageCircle className="h-5 w-5" />{t("transplant.sendWhatsapp", "Send on WhatsApp")}</a>
          <a className="btn-outline" href={links.tg} target="_blank" rel="noreferrer"><Send className="h-4 w-4" />Telegram</a>
          <a className="btn-outline" href={links.sms}><MessageCircle className="h-4 w-4" />SMS</a>
          <a className="btn-outline" href={links.mail}><Mail className="h-4 w-4" />Email</a>
          <button className="btn-outline" onClick={copy} data-testid="copy-msg">{copied ? <Check className="h-4 w-4 text-ok" /> : <Copy className="h-4 w-4" />}{copied ? t("transplant.copied", "Copied") : t("transplant.copy", "Copy")}</button>
          {canShare && <button className="btn-outline" onClick={nativeShare}><Share2 className="h-4 w-4" />{t("transplant.share", "Share")}</button>}
        </div>
        <p className="text-xs text-muted">{t("transplant.waHint", "WhatsApp opens with the message ready. Pick a group or any contact and tap send. Nothing is sent without you.")}</p>

        <div className="card p-4">
          <p className="mb-2 flex items-center gap-2 font-semibold"><UserPlus className="h-4 w-4 text-accent" />{t("transplant.contactsTitle", "Send to people one by one")}</p>
          <textarea className="input min-h-[80px]" placeholder={t("transplant.contactsPlaceholder", "Paste one per line: Name, phone") as string} value={raw} onChange={(e) => setRaw(e.target.value)} data-testid="contacts-raw" />
          <div className="mt-2 flex items-center justify-between gap-2">
            <p className="text-xs text-muted">{t("transplant.contactsPrivacy", "Saved only in this browser.")}</p>
            <button className="btn-soft" onClick={() => { const add = parseContacts(raw); if (!add.length) return notify.errorText(t("transplant.noNumbers", "No phone numbers found") as string); persist([...contacts, ...add]); setRaw(""); }} data-testid="contacts-add">{t("transplant.addContacts", "Add")}</button>
          </div>
          {contacts.length > 0 && (
            <ul className="mt-3 max-h-56 space-y-1 overflow-auto">
              {contacts.map((c) => (
                <li key={c.id} className="flex items-center gap-2 rounded-xl px-2 py-1 hover:bg-[var(--surface-2)]">
                  <span className="min-w-0 flex-1 truncate text-sm"><b>{c.name}</b> <span className="text-muted">{c.phone}</span></span>
                  <a href={waLink(text, c.phone)} target="_blank" rel="noreferrer" onClick={() => persist(contacts.map((x) => x.id === c.id ? { ...x, sent: true } : x))}
                    className={cn("btn-soft !min-h-[36px] !px-3 text-sm", c.sent && "opacity-60")}>{c.sent ? <Check className="h-4 w-4" /> : <MessageCircle className="h-4 w-4" />}{c.sent ? t("transplant.sentAgain", "Again") : "WhatsApp"}</a>
                  <button aria-label="remove" className="text-muted hover:text-danger" onClick={() => persist(contacts.filter((x) => x.id !== c.id))}><Trash2 className="h-4 w-4" /></button>
                </li>
              ))}
            </ul>
          )}
        </div>

        {publicUrl && (
          <div className="card flex flex-wrap items-center gap-4 p-4">
            <QR value={publicUrl} size={110} />
            <div className="min-w-0 flex-1">
              <p className="font-semibold">{t("transplant.publicLink", "Public page for this request")}</p>
              <p className="break-all text-xs text-muted">{publicUrl}</p>
              <button className="btn-ghost mt-1 !px-2" onClick={() => window.print()}><Printer className="h-4 w-4" />{t("transplant.printFlyer", "Print flyer with QR")}</button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
