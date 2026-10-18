import * as Popover from "@radix-ui/react-popover";
import { useQuery } from "@tanstack/react-query";
import { Bell } from "lucide-react";
import { useTranslation } from "react-i18next";
import { Link, useNavigate } from "react-router-dom";
import { api, type Notification, type Role } from "@/lib/api";
import { relTime } from "@/lib/utils";
import { useSession } from "@/store/session";
import { useState } from "react";

export function notificationLink(n: Notification, role: Role): string {
  switch (n.kind) {
    case "rx_submitted": return `/doctor/rx/${n.payload.prescription_id}`;
    case "rx_signed":
    case "rx_rejected": return `/rx?open=${n.payload.prescription_id}`;
    case "patient_linked": return `/doctor/patients/${n.payload.patient_id}`;
    case "message": return `/chat/${n.payload.thread_id}`;
    default: return role === "doctor" ? "/doctor" : "/notifications";
  }
}

export function useUnread() {
  const user = useSession((s) => s.user);
  return useQuery({
    queryKey: ["notifications", "unread"],
    queryFn: () => api.notifications(true),
    enabled: !!user,
    refetchInterval: () => (document.hidden ? false : 30000),
  });
}

export function NotificationBell() {
  const { t, i18n } = useTranslation();
  const nav = useNavigate();
  const user = useSession((s) => s.user)!;
  const { data = [], refetch } = useUnread();
  const [open, setOpen] = useState(false);
  const count = data.length;

  return (
    <Popover.Root open={open} onOpenChange={setOpen}>
      <Popover.Trigger asChild>
        <button className="btn-ghost relative !px-3" aria-label={t("nav.notifications")} data-testid="bell">
          <Bell className="h-5 w-5" />
          {count > 0 && <span className="absolute right-1 top-1 grid h-5 min-w-[20px] place-items-center rounded-full bg-danger px-1 text-[11px] font-bold text-white">{count > 9 ? "9+" : count}</span>}
        </button>
      </Popover.Trigger>
      <Popover.Portal>
        <Popover.Content align="end" sideOffset={8} className="card z-[80] w-[min(92vw,360px)] p-2 shadow-lift">
          <p className="px-3 py-2 text-sm font-semibold">{t("notifications.title")}</p>
          {data.length === 0 && <p className="px-3 py-6 text-center text-sm text-muted">{t("notifications.empty")}</p>}
          <div className="max-h-80 overflow-y-auto">
            {data.slice(0, 8).map((n) => (
              <button key={n.id} className="block w-full rounded-xl px-3 py-2 text-left hover:bg-slate-50"
                onClick={async () => { setOpen(false); await api.markRead(n.id).catch(() => {}); void refetch(); nav(notificationLink(n, user.role)); }}>
                <span className="block text-sm font-semibold">{t(`notifications.kinds.${n.kind}`, { defaultValue: n.title })}</span>
                {n.body && <span className="block truncate text-xs text-muted">{n.body}</span>}
                <span className="text-xs text-muted">{relTime(n.created_at, i18n.language)}</span>
              </button>
            ))}
          </div>
          <Link to="/notifications" onClick={() => setOpen(false)} className="block rounded-xl px-3 py-2 text-center text-sm font-semibold text-accent hover:bg-slate-50">{t("app.learnMore")}</Link>
        </Popover.Content>
      </Popover.Portal>
    </Popover.Root>
  );
}
