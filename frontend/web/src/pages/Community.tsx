import { Tx } from "@/lib/translate";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Flag, Send, Trash2 } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { Chip, EmptyState, ErrorState, LoadingBlock, PageHeader, Spinner, useNotify } from "@/components/ui";
import { api } from "@/lib/api";
import { cn, fmtTime } from "@/lib/utils";

export default function Community() {
  const { t, i18n } = useTranslation();
  const qc = useQueryClient();
  const notify = useNotify();
  const [active, setActive] = useState<number | null>(null);
  const [text, setText] = useState("");
  const bottom = useRef<HTMLDivElement>(null);
  const chans = useQuery({ queryKey: ["channels"], queryFn: () => api.channels() });
  useEffect(() => { if (active === null && chans.data?.length) setActive(chans.data[0].id); }, [chans.data, active]);
  const posts = useQuery({ queryKey: ["posts", active], queryFn: () => api.channelPosts(active!), enabled: active !== null, refetchInterval: 6000 });
  useEffect(() => { bottom.current?.scrollIntoView({ behavior: "smooth" }); }, [posts.data?.length, active]);

  const send = useMutation({ mutationFn: () => api.addPost(active!, text.trim()), onSuccess: () => { setText(""); void qc.invalidateQueries({ queryKey: ["posts", active] }); void qc.invalidateQueries({ queryKey: ["channels"] }); }, onError: (e) => notify.error(e) });
  const del = useMutation({ mutationFn: (id: number) => api.deletePost(id), onSuccess: () => void qc.invalidateQueries({ queryKey: ["posts", active] }), onError: (e) => notify.error(e) });
  const rep = useMutation({ mutationFn: (id: number) => api.reportPost(id), onSuccess: () => { notify.ok(t("community.reported")); void qc.invalidateQueries({ queryKey: ["posts", active] }); }, onError: (e) => notify.error(e) });

  if (chans.isLoading) return <LoadingBlock />;
  if (chans.error) return <ErrorState error={chans.error} onRetry={() => chans.refetch()} />;
  const ch = chans.data!.find((c) => c.id === active);
  const name = (slug: string) => t(`community.channelNames.${slug}`, { defaultValue: slug });

  return (
    <>
      <PageHeader title={t("community.title")} subtitle={t("community.intro")} />
      <div className="grid gap-4 md:grid-cols-[240px_minmax(0,1fr)]" style={{ height: "calc(100vh - 13rem)", minHeight: 460 }}>
        <div className="card overflow-y-auto p-2" data-testid="channels">
          <p className="px-3 py-2 text-xs font-bold uppercase tracking-wider text-muted">{t("community.channels")}</p>
          {chans.data!.map((c) => (
            <button key={c.id} onClick={() => setActive(c.id)} data-testid={`channel-${c.slug}`} className={cn("flex min-h-[44px] w-full items-center justify-between rounded-xl px-3 text-left font-medium", active === c.id ? "bg-accent text-white" : "hover:bg-slate-100")}>
              <span># {name(c.slug)}</span><span className={cn("text-xs", active === c.id ? "text-white/80" : "text-muted")}>{c.posts}</span>
            </button>
          ))}
        </div>
        <div className="flex min-h-0 flex-col overflow-hidden rounded-xl2 border border-line bg-white">
          <div className="border-b border-line px-4 py-3"><p className="font-bold"># {ch ? name(ch.slug) : ""}</p><p className="text-sm text-muted">{ch ? t(`community.channelDesc.${ch.slug}`, { defaultValue: ch.description }) : ""}</p></div>
          <div className="flex-1 space-y-3 overflow-y-auto bg-slate-50 p-4" data-testid="posts">
            {posts.isLoading && <div className="grid place-items-center py-6"><Spinner /></div>}
            {posts.data && posts.data.length === 0 && <EmptyState title={t("community.empty")} />}
            {(posts.data ?? []).map((p) => (
              <div key={p.id} className="flex gap-3" data-testid="post">
                <span className="grid h-9 w-9 shrink-0 place-items-center rounded-full bg-accent-soft font-bold">{p.author.slice(0, 1).toUpperCase()}</span>
                <div className="min-w-0 flex-1">
                  <p className="flex flex-wrap items-center gap-2 text-sm"><b>{p.mine ? t("community.you") : p.author}</b>{p.author_role === "doctor" && <Chip tone="info">{t("community.doctorBadge")}</Chip>}<span className="text-xs text-muted">{fmtTime(p.created_at, i18n.language)}</span></p>
                  <Tx as="p" className="whitespace-pre-wrap break-words" text={p.body} />
                </div>
                <div className="flex shrink-0 gap-1">
                  {!p.mine && <button className="rounded-full p-2 text-muted hover:bg-slate-100" aria-label={t("community.report")} title={t("community.report")} onClick={() => rep.mutate(p.id)}><Flag className="h-4 w-4" /></button>}
                  {p.mine && <button className="rounded-full p-2 text-muted hover:bg-slate-100" aria-label={t("community.delete")} title={t("community.delete")} onClick={() => del.mutate(p.id)}><Trash2 className="h-4 w-4" /></button>}
                </div>
              </div>
            ))}
            <div ref={bottom} />
          </div>
          <form className="border-t border-line p-3" onSubmit={(e) => { e.preventDefault(); if (text.trim()) send.mutate(); }}>
            <div className="flex gap-2"><input data-testid="post-input" className="input" placeholder={t("community.write")} maxLength={1000} value={text} onChange={(e) => setText(e.target.value)} />
              <button className="btn-primary !px-4" disabled={send.isPending || !text.trim()} aria-label={t("community.post")} data-testid="post-send">{send.isPending ? <Spinner className="text-white" /> : <Send className="h-5 w-5" />}</button></div>
            <p className="mt-1 text-xs text-muted">{t("community.rules")}</p>
          </form>
        </div>
      </div>
    </>
  );
}
