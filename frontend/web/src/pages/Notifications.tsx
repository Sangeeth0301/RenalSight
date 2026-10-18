import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Bell, CheckCheck, Mail, Pill, UserPlus } from "lucide-react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";
import { notificationLink } from "@/components/NotificationBell";
import { Card, EmptyState, ErrorState, LoadingBlock, PageHeader, useNotify } from "@/components/ui";
import { api, type Notification } from "@/lib/api";
import { cn, relTime } from "@/lib/utils";
import { useSession } from "@/store/session";

const ICON: Record<Notification["kind"], typeof Bell> = { rx_submitted: Pill, rx_signed: Pill, rx_rejected: Pill, patient_linked: UserPlus, message: Mail };

export default function Notifications() {
  const { t, i18n } = useTranslation();
  const nav = useNavigate();
  const qc = useQueryClient();
  const notify = useNotify();
  const user = useSession((s) => s.user)!;
  const q = useQuery({ queryKey: ["notifications", "all"], queryFn: () => api.notifications(), refetchInterval: 30000 });

  const open = async (n: Notification) => {
    try { if (!n.read) await api.markRead(n.id); } catch { /* ignore */ }
    void qc.invalidateQueries({ queryKey: ["notifications"] });
    nav(notificationLink(n, user.role));
  };
  const all = async () => { try { await api.markAllRead(); void qc.invalidateQueries({ queryKey: ["notifications"] }); } catch (e) { notify.error(e); } };

  return (
    <>
      <PageHeader title={t("notifications.title")} right={<button className="btn-outline" onClick={all} data-testid="mark-all"><CheckCheck className="h-4 w-4" />{t("notifications.markAll")}</button>} />
      {q.isLoading ? <LoadingBlock /> : q.error ? <ErrorState error={q.error} onRetry={() => q.refetch()} /> : (q.data ?? []).length === 0 ? <EmptyState title={t("notifications.empty")} icon={<Bell className="h-7 w-7" />} /> : (
        <div className="space-y-2" data-testid="notification-list">
          {(q.data ?? []).map((n) => {
            const Icon = ICON[n.kind] ?? Bell;
            return (
              <button key={n.id} onClick={() => open(n)} className={cn("card flex w-full items-start gap-3 p-4 text-left transition hover:shadow-lift", !n.read && "border-accent/50 bg-accent-soft/40")} data-testid="notification">
                <span className="grid h-10 w-10 shrink-0 place-items-center rounded-full bg-accent-soft text-accent"><Icon className="h-5 w-5" /></span>
                <span className="min-w-0 flex-1"><span className="block font-semibold">{t(`notifications.kinds.${n.kind}`, { defaultValue: n.title })}</span>{n.body && <span className="block text-sm text-muted">{n.body}</span>}<span className="text-xs text-muted">{relTime(n.created_at, i18n.language)}</span></span>
                {!n.read && <span className="mt-2 h-2.5 w-2.5 rounded-full bg-danger" aria-label="unread" />}
              </button>
            );
          })}
        </div>
      )}
      <Card className="mt-6 hidden" />
    </>
  );
}
