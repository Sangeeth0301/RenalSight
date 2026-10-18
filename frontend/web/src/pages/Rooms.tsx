import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Copy, DoorOpen, LogOut, Plus, RefreshCw, Trash2 } from "lucide-react";
import { useRef, useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";
import { Link, useNavigate, useParams } from "react-router-dom";
import { ChatPane } from "@/components/ChatPane";
import { Card, Chip, EmptyState, ErrorState, Field, LoadingBlock, Modal, PageHeader, Spinner, useNotify } from "@/components/ui";
import { api, ApiError } from "@/lib/api";
import { fmtTime } from "@/lib/utils";
import { useSession } from "@/store/session";

function OtpInput({ value, onChange }: { value: string; onChange: (v: string) => void }) {
  const refs = useRef<(HTMLInputElement | null)[]>([]);
  const digits = value.padEnd(6, " ").split("");
  const set = (i: number, d: string) => {
    const arr = value.padEnd(6, " ").split("");
    arr[i] = d || " ";
    onChange(arr.join("").replace(/\s+$/, ""));
    if (d && i < 5) refs.current[i + 1]?.focus();
  };
  return (
    <div className="flex justify-center gap-2" onPaste={(e) => { const p = e.clipboardData.getData("text").replace(/\D/g, "").slice(0, 6); if (p) { e.preventDefault(); onChange(p); refs.current[Math.min(p.length, 5)]?.focus(); } }}>
      {digits.map((d, i) => (
        <input key={i} ref={(el) => (refs.current[i] = el)} data-testid={`otp-${i}`} inputMode="numeric" maxLength={1} aria-label={`digit ${i + 1}`}
          className="h-14 w-11 rounded-xl border-2 border-line bg-white text-center text-2xl font-bold focus:border-accent sm:w-12" value={d.trim()}
          onChange={(e) => set(i, e.target.value.replace(/\D/g, "").slice(-1))}
          onKeyDown={(e) => { if (e.key === "Backspace" && !d.trim() && i > 0) refs.current[i - 1]?.focus(); }} />
      ))}
    </div>
  );
}

export default function Rooms() {
  const { id } = useParams();
  return id ? <RoomView id={Number(id)} /> : <Lobby />;
}

function Lobby() {
  const { t } = useTranslation();
  const nav = useNavigate();
  const qc = useQueryClient();
  const notify = useNotify();
  const [code, setCode] = useState("");
  const [title, setTitle] = useState("");
  const [err, setErr] = useState("");
  const threads = useQuery({ queryKey: ["threads"], queryFn: () => api.threads() });
  const rooms = (threads.data ?? []).filter((x) => x.kind === "room");

  const join = useMutation({
    mutationFn: () => api.joinRoom(code),
    onSuccess: async (r) => { await qc.invalidateQueries({ queryKey: ["threads"] }); nav(`/rooms/${r.id}`); },
    onError: (e) => {
      if (e instanceof ApiError && e.status === 404) setErr(t("room.invalid"));
      else if (e instanceof ApiError && e.status === 409) setErr(t("room.full"));
      else if (e instanceof ApiError && e.status === 429) setErr(t("room.tooMany"));
      else notify.error(e);
    },
  });
  const create = useMutation({
    mutationFn: () => api.createRoom(title.trim()),
    onSuccess: async (r) => { await qc.invalidateQueries({ queryKey: ["threads"] }); nav(`/rooms/${r.id}`); },
    onError: (e) => notify.error(e),
  });

  return (
    <>
      <PageHeader title={t("room.title")} subtitle={t("room.intro")} />
      <div className="grid gap-6 md:grid-cols-2">
        <Card className="space-y-4">
          <h2 className="flex items-center gap-2 text-lg font-bold"><DoorOpen className="h-5 w-5 text-accent" />{t("room.join")}</h2>
          <OtpInput value={code} onChange={(v) => { setCode(v); setErr(""); }} />
          {err && <p className="text-center text-sm font-medium text-danger" data-testid="join-error">{err}</p>}
          <button className="btn-primary w-full" disabled={code.length !== 6 || join.isPending} onClick={() => join.mutate()} data-testid="join-room">{join.isPending ? <Spinner className="text-white" /> : t("room.enter")}</button>
        </Card>
        <Card className="space-y-4">
          <h2 className="flex items-center gap-2 text-lg font-bold"><Plus className="h-5 w-5 text-accent" />{t("room.create")}</h2>
          <form onSubmit={(e: FormEvent) => { e.preventDefault(); if (title.trim()) create.mutate(); }} className="space-y-3">
            <Field label={t("room.roomName")}><input data-testid="room-title" className="input" maxLength={120} value={title} onChange={(e) => setTitle(e.target.value)} /></Field>
            <button className="btn-soft w-full" disabled={!title.trim() || create.isPending} data-testid="create-room">{create.isPending ? <Spinner /> : t("room.create")}</button>
          </form>
        </Card>
      </div>
      <h2 className="mb-3 mt-8 text-lg font-bold">{t("nav.consultRoom")}</h2>
      {threads.isLoading ? <LoadingBlock rows={2} /> : rooms.length === 0 ? <EmptyState title={t("chat.none")} /> : (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {rooms.map((r) => (
            <Link key={r.id} to={`/rooms/${r.id}`} className="card p-4 transition hover:shadow-lift" data-testid="room-card">
              <div className="flex items-center justify-between"><p className="font-bold">{r.title}</p>{r.unread > 0 && <Chip tone="danger">{r.unread}</Chip>}</div>
              <p className="mt-1 text-sm text-muted">{r.members.map((m) => m.name).join(", ")}</p>
            </Link>
          ))}
        </div>
      )}
    </>
  );
}

function RoomView({ id }: { id: number }) {
  const { t, i18n } = useTranslation();
  const nav = useNavigate();
  const qc = useQueryClient();
  const notify = useNotify();
  const user = useSession((s) => s.user)!;
  const [task, setTask] = useState("");
  const [confirm, setConfirm] = useState(false);
  const threads = useQuery({ queryKey: ["threads"], queryFn: () => api.threads(), refetchInterval: 15000 });
  const room = (threads.data ?? []).find((x) => x.id === id);
  const tasks = useQuery({ queryKey: ["tasks", id], queryFn: () => api.roomTasks(id), refetchInterval: 8000, enabled: !!room });
  const owner = !!room?.code;

  const addTask = useMutation({ mutationFn: (txt: string) => api.addRoomTask(id, txt), onSuccess: () => { setTask(""); void qc.invalidateQueries({ queryKey: ["tasks", id] }); }, onError: (e) => notify.error(e) });
  const toggle = useMutation({ mutationFn: (v: { id: number; done: boolean }) => api.setRoomTask(id, v.id, v.done), onSuccess: () => void qc.invalidateQueries({ queryKey: ["tasks", id] }), onError: (e) => notify.error(e) });
  const regen = useMutation({ mutationFn: () => api.newRoomCode(id), onSuccess: () => void qc.invalidateQueries({ queryKey: ["threads"] }), onError: (e) => notify.error(e) });
  const leave = useMutation({ mutationFn: () => api.leaveRoom(id), onSuccess: async () => { await qc.invalidateQueries({ queryKey: ["threads"] }); nav("/rooms"); }, onError: (e) => notify.error(e) });
  const close = useMutation({ mutationFn: () => api.closeRoom(id), onSuccess: async () => { await qc.invalidateQueries({ queryKey: ["threads"] }); nav("/rooms"); }, onError: (e) => notify.error(e) });

  if (threads.isLoading) return <LoadingBlock />;
  if (threads.error) return <ErrorState error={threads.error} onRetry={() => threads.refetch()} />;
  if (!room) return <EmptyState title={t("errors.notFound")} action={<Link to="/rooms" className="btn-primary">{t("app.back")}</Link>} />;

  return (
    <>
      <Link to="/rooms" className="btn-ghost mb-3"><ArrowLeft className="h-4 w-4" />{t("app.back")}</Link>
      <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_340px]" style={{ minHeight: 520 }}>
        <div style={{ height: "calc(100vh - 11rem)", minHeight: 480 }}>
          <ChatPane key={room.id} thread={room} onClosed={() => { void qc.invalidateQueries({ queryKey: ["threads"] }); nav("/rooms"); }}
            onEvent={(ev) => { if (ev.type === "task") void qc.invalidateQueries({ queryKey: ["tasks", id] }); if (ev.type === "presence" && ev.joined) void qc.invalidateQueries({ queryKey: ["threads"] }); }} />
        </div>
        <div className="space-y-4">
          {owner && (
            <Card className="text-center" data-testid="room-code-card">
              <p className="text-sm font-medium text-muted">{t("room.yourCode")}</p>
              <p className="my-2 select-all text-4xl font-extrabold tracking-[0.3em]" data-testid="room-code">{room.code}</p>
              {room.code_expires_at && <p className="text-xs text-muted">{t("room.expires", { time: fmtTime(room.code_expires_at, i18n.language) })}</p>}
              <div className="mt-3 flex justify-center gap-2">
                <button className="btn-outline" onClick={() => { void navigator.clipboard?.writeText(room.code!); notify.ok(room.code!); }}><Copy className="h-4 w-4" /></button>
                <button className="btn-outline" onClick={() => regen.mutate()} disabled={regen.isPending}><RefreshCw className="h-4 w-4" />{t("room.regenerate")}</button>
              </div>
            </Card>
          )}
          <Card>
            <h3 className="mb-2 font-bold">{t("room.members")} ({room.members.length})</h3>
            <ul className="space-y-2">{room.members.map((m) => (
              <li key={m.id} className="flex items-center gap-2"><span className="grid h-8 w-8 place-items-center rounded-full bg-accent-soft text-sm font-bold">{m.name.slice(0, 1).toUpperCase()}</span>
                <span className="flex-1 truncate">{m.name}{m.id === user.id ? " (you)" : ""}</span><Chip>{t(`roles.${m.role}`)}</Chip>{m.online && <span className="h-2.5 w-2.5 rounded-full bg-ok" />}</li>
            ))}</ul>
          </Card>
          <Card>
            <h3 className="mb-2 font-bold">{t("room.tasks")}</h3>
            <ul className="space-y-1" data-testid="tasks">
              {(tasks.data ?? []).map((x) => (
                <li key={x.id}><label className="flex min-h-[40px] cursor-pointer items-center gap-2"><input type="checkbox" className="h-5 w-5 accent-[var(--accent)]" checked={x.done} onChange={(e) => toggle.mutate({ id: x.id, done: e.target.checked })} /><span className={x.done ? "text-muted line-through" : ""}>{x.text}</span></label></li>
              ))}
            </ul>
            <form className="mt-2 flex gap-2" onSubmit={(e) => { e.preventDefault(); if (task.trim()) addTask.mutate(task.trim()); }}>
              <input data-testid="task-input" className="input" placeholder={t("room.addTask")} maxLength={300} value={task} onChange={(e) => setTask(e.target.value)} />
              <button className="btn-soft !px-3" aria-label={t("room.addTask")}><Plus className="h-5 w-5" /></button>
            </form>
          </Card>
          {owner ? <button className="btn-outline w-full text-danger" onClick={() => setConfirm(true)} data-testid="close-room"><Trash2 className="h-4 w-4" />{t("room.close")}</button>
            : <button className="btn-outline w-full" onClick={() => leave.mutate()}><LogOut className="h-4 w-4" />{t("room.leave")}</button>}
        </div>
      </div>
      <Modal open={confirm} onClose={() => setConfirm(false)} title={t("room.close")}>
        <p className="mb-4">{t("room.confirmClose")}</p>
        <div className="flex justify-end gap-2"><button className="btn-outline" onClick={() => setConfirm(false)}>{t("app.cancel")}</button><button className="btn-danger" onClick={() => close.mutate()} data-testid="confirm-close">{t("room.close")}</button></div>
      </Modal>
    </>
  );
}
