import { useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, MessageCircle } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { ChatPane } from "@/components/ChatPane";
import { Card, Chip, EmptyState, ErrorState, LoadingBlock, PageHeader, useNotify } from "@/components/ui";
import { api, type AttachmentInput } from "@/lib/api";
import { cn, fmtTime, stageColor } from "@/lib/utils";
import { useSession } from "@/store/session";
import { Tx } from "@/lib/translate";

export default function Chat() {
  const { t, i18n } = useTranslation();
  const { threadId } = useParams();
  const [sp] = useSearchParams();
  const nav = useNavigate();
  const qc = useQueryClient();
  const notify = useNotify();
  const user = useSession((s) => s.user)!;
  const q = useQuery({ queryKey: ["threads"], queryFn: () => api.threads(), refetchInterval: 20000 });
  const isDoc = user.role === "doctor";
  const pts = useQuery({ queryKey: ["doctor", "patients"], queryFn: () => api.doctorPatients(), enabled: isDoc });
  const byId = useMemo(() => new Map((pts.data ?? []).map((p) => [p.id, p])), [pts.data]);
  const [find, setFind] = useState("");
  const startWith = async (pid: number) => {
    try { const th = await api.openDirect(pid); await qc.invalidateQueries({ queryKey: ["threads"] }); setFind(""); nav(`/chat/${th.id}`); } catch (e) { notify.error(e); }
  };
  const matches = find.trim().length > 0 ? (pts.data ?? []).filter((p) => p.name.toLowerCase().includes(find.toLowerCase())).slice(0, 6) : [];
  const direct = (q.data ?? []).filter((x) => x.kind === "direct");
  const active = useMemo(() => (q.data ?? []).find((x) => x.id === Number(threadId)), [q.data, threadId]);
  const share: AttachmentInput | null = sp.get("share") === "kidney" ? { type: "kidney_snapshot" } : null;

  // desktop: open the first conversation automatically
  useEffect(() => {
    if (!threadId && direct.length > 0 && window.matchMedia("(min-width: 1024px)").matches) nav(`/chat/${direct[0].id}${share ? "?share=kidney" : ""}`, { replace: true });
  }, [threadId, direct.length]); // eslint-disable-line react-hooks/exhaustive-deps

  // patient with a linked doctor but no thread yet: open it on demand
  const openWithDoctor = async () => {
    try {
      const th = await api.openDirect(user.doctor_id!);
      await qc.invalidateQueries({ queryKey: ["threads"] });
      nav(`/chat/${th.id}${share ? "?share=kidney" : ""}`);
    } catch (e) { notify.error(e); }
  };
  useEffect(() => {
    if (user.role === "patient" && user.doctor_id && q.data && direct.length === 0 && sp.get("share")) void openWithDoctor();
  }, [q.data]); // eslint-disable-line react-hooks/exhaustive-deps

  if (q.isLoading) return <LoadingBlock />;
  if (q.error) return <ErrorState error={q.error} onRetry={() => q.refetch()} />;
  const threads = q.data ?? [];
  if (threadId && !active) return <EmptyState title={t("errors.notFound")} action={<Link to="/chat" className="btn-primary">{t("app.back")}</Link>} icon={<MessageCircle className="h-7 w-7" />} />;

  const list = (
    <div className="space-y-2" data-testid="thread-list">
      {isDoc && (
        <div className="relative mb-1">
          <input className="input" placeholder="Message a patient..." value={find} onChange={(e) => setFind(e.target.value)} data-testid="chat-find" />
          {matches.length > 0 && <ul className="card absolute z-30 mt-1 w-full p-1">{matches.map((p) => <li key={p.id}><button className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-left hover:bg-[var(--surface-2)]" onClick={() => void startWith(p.id)}><span className="min-w-0 flex-1 truncate font-medium">{p.name}</span>{p.state.g_stage && <span className="chip text-white" style={{ background: stageColor(p.state.g_stage) }}>{p.state.g_stage}</span>}</button></li>)}</ul>}
        </div>
      )}
      {threads.map((th) => {
        const other = th.members.find((m) => m.id !== user.id);
        return (
          <Link key={th.id} to={`/chat/${th.id}`} data-testid="thread" className={cn("card flex items-center gap-3 p-3 transition hover:shadow-lift", Number(threadId) === th.id && "!border-accent ring-2 ring-accent/30")}>
            <div className="relative grid h-11 w-11 shrink-0 place-items-center rounded-full bg-accent-soft font-bold">{th.title.slice(0, 1).toUpperCase()}
              {other?.online && <span className="absolute bottom-0 right-0 h-3 w-3 rounded-full border-2 border-white bg-ok" />}</div>
            <div className="min-w-0 flex-1"><div className="flex items-baseline justify-between gap-2"><p className="flex items-center gap-1.5 truncate font-semibold">{th.title}{isDoc && other && byId.get(other.id)?.state.g_stage && <span className="chip text-white" style={{ background: stageColor(byId.get(other.id)!.state.g_stage) }}>{byId.get(other.id)!.state.g_stage}</span>}{isDoc && other && byId.get(other.id)?.state.urgent && <span className="h-2 w-2 rounded-full bg-danger" title="Urgent" />}</p>{th.last_message && <span className="shrink-0 text-xs text-muted">{fmtTime(th.last_message.created_at, i18n.language)}</span>}</div>
              <p className="truncate text-sm text-muted">{th.last_message ? <>{th.last_message.kind === "attachment" ? "📎 " : ""}<Tx text={th.last_message.body || ""} /></> : ""}</p></div>
            {th.unread > 0 && <Chip tone="danger">{th.unread}</Chip>}
          </Link>
        );
      })}
      {user.role === "patient" && user.doctor_id && direct.length === 0 && <button className="btn-primary w-full" onClick={openWithDoctor} data-testid="open-doctor"><MessageCircle className="h-4 w-4" />{t("chat.openWithDoctor")}</button>}
    </div>
  );

  return (
    <>
      <div className={threadId ? "hidden lg:block" : ""}><PageHeader title={user.role === "doctor" ? t("nav.messages") : t("chat.directLine")} /></div>
      {user.role === "patient" && !user.doctor_id && threads.length === 0 ? (
        <EmptyState title={t("chat.linkFirst")} action={<Link to="/settings" className="btn-primary">{t("onboarding.linkDoctor")}</Link>} icon={<MessageCircle className="h-7 w-7" />} />
      ) : (
        <div className="grid gap-4 lg:grid-cols-[320px_minmax(0,1fr)]" style={{ height: "calc(100vh - 11rem)", minHeight: 480 }}>
          <div className={cn("overflow-y-auto", threadId ? "hidden lg:block" : "")}>{threads.length === 0 && !(user.role === "patient" && user.doctor_id) ? <EmptyState title={t("chat.none")} /> : list}</div>
          <div className={cn("min-h-0", !threadId && "hidden lg:block")}>
            {threadId && <Link to="/chat" className="btn-ghost mb-2 lg:hidden"><ArrowLeft className="h-4 w-4" />{t("app.back")}</Link>}
            {active ? <ChatPane key={active.id} thread={active} initialAttachment={share} /> : threadId ? <EmptyState title={t("errors.notFound")} /> : <Card className="hidden h-full place-items-center text-muted lg:grid">{t("chat.none")}</Card>}
          </div>
        </div>
      )}
    </>
  );
}
