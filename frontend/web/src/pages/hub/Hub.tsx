import { useQuery } from "@tanstack/react-query";
import { Send, Activity, Building2, ClipboardCheck, Heart, HeartHandshake, IdCard, Share2, ShieldAlert, Users } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import { Card, Chip, EmptyState, LoadingBlock, PageHeader } from "@/components/ui";
import { api } from "@/lib/api";
import { fmtDate } from "@/lib/utils";
import { useSession } from "@/store/session";

export default function Hub() {
  const { t, i18n } = useTranslation();
  const user = useSession((s) => s.user)!;
  const staff = user.role === "doctor" || user.role === "admin";
  const meta = useQuery({ queryKey: ["tx", "meta"], queryFn: () => api.txMeta() });
  const stats = useQuery({ queryKey: ["tx", "stats"], queryFn: () => api.donorStats() });
  const mine = useQuery({ queryKey: ["tx", "requests"], queryFn: () => api.requests(), enabled: !staff });
  const [bg, setBg] = useState("B+");
  const compat = useQuery({ queryKey: ["tx", "compat", bg], queryFn: () => api.compat(bg) });

  const tiles = [
    ...(!staff ? [{ to: "/hub/request/new", icon: Share2, title: t("transplant.tileRequest", "Ask for a kidney donor"), body: t("transplant.tileRequestBody", "Type the hospital and patient. We write the message and open WhatsApp."), testid: "tile-request" }] : []),
    { to: "/hub/broadcast", icon: Send, title: "WhatsApp messages", body: "Send reminders, updates and appeals to groups or to each person, in 4 languages.", testid: "tile-broadcast" },
    { to: "/hub/donate", icon: HeartHandshake, title: t("transplant.tileDonate", "Pledge to donate"), body: t("transplant.tileDonateBody", "Kidney (living) or kidney, heart, liver and eyes after death. Free, voluntary, reversible."), testid: "tile-donate" },
    { to: "/hub/hospitals", icon: Building2, title: t("transplant.tileHospitals", "Hospitals and dialysis seats"), body: t("transplant.tileHospitalsBody", "Find AIIMS, KMCH and 30+ transplant hospitals; see free dialysis seats."), testid: "tile-hospitals" },
    { to: "/hub/journey", icon: ClipboardCheck, title: t("transplant.tileJourney", "Transplant journey"), body: t("transplant.tileJourneyBody", "A 10-step checklist from specialist review to follow-up."), testid: "tile-journey" },
    { to: "/hub/dialysis", icon: Activity, title: t("transplant.tileDialysis", "Dialysis log"), body: t("transplant.tileDialysisBody", "Weights, blood pressure and sessions, with a fluid-gain warning."), testid: "tile-dialysis" },
    { to: "/hub/id", icon: IdCard, title: t("transplant.tileId", "Emergency ID and exports"), body: t("transplant.tileIdBody", "QR emergency card, FHIR file and referral letter PDF for any hospital."), testid: "tile-id" },
    ...(staff ? [{ to: "/hub/desk", icon: Users, title: "Coordinator desk", body: "Verify donor requests, update dialysis seat availability.", testid: "tile-desk" }] : []),
  ];

  return (
    <div className="space-y-6">
      <PageHeader title={t("transplant.title", "Transplant and donor hub")} subtitle={t("transplant.subtitle", "Find donors, share appeals safely, and keep every hospital step in one place.")} />
      <div className="card flex items-start gap-3 border-amber-300/60 p-4" role="note">
        <ShieldAlert className="mt-0.5 h-5 w-5 shrink-0 text-warn" />
        <p className="text-sm">{meta.data?.safety[0] ?? t("transplant.safety", "Organs are never bought or sold. Anyone asking for money is a scam.")} <span className="text-muted">{meta.data?.safety[2]}</span></p>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {tiles.map((x) => (
          <Link key={x.to} to={x.to} className="bento block" data-testid={x.testid}>
            <div className="mb-3 grid h-12 w-12 place-items-center rounded-xl2 text-white" style={{ backgroundImage: "linear-gradient(135deg,var(--accent),var(--accent-2))" }}><x.icon className="h-6 w-6" /></div>
            <h3 className="font-display text-lg font-bold">{x.title}</h3>
            <p className="mt-1 text-sm text-muted">{x.body}</p>
          </Link>
        ))}
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <h2 className="mb-3 flex items-center gap-2 text-lg font-bold"><Heart className="h-5 w-5 text-danger" />{t("transplant.compatTitle", "Who can donate a kidney to me?")}</h2>
          <div className="flex flex-wrap gap-2">
            {(meta.data?.blood_groups ?? ["O-", "O+", "A-", "A+", "B-", "B+", "AB-", "AB+"]).map((g) => (
              <button key={g} onClick={() => setBg(g)} data-testid={`bg-${g}`} className={`min-h-[40px] min-w-[52px] rounded-xl border px-3 font-bold transition ${bg === g ? "border-transparent text-[color:var(--on-accent)]" : "border-line"}`}
                style={bg === g ? { backgroundImage: "linear-gradient(135deg,var(--accent),var(--accent-2))" } : undefined}>{g}</button>
            ))}
          </div>
          <p className="mt-4 text-lg" data-testid="compat-result">{t("transplant.compatResult", "Blood groups that can donate to {{g}}:", { g: bg })} <b>{compat.data?.donor_groups.join(", ")}</b></p>
          <p className="mt-1 text-xs text-muted">{compat.data?.note}</p>
        </Card>

        <Card>
          <h2 className="mb-3 text-lg font-bold">{t("transplant.community", "Community pledges")}</h2>
          {stats.isLoading ? <LoadingBlock rows={2} /> : (
            <div className="grid grid-cols-3 gap-3 text-center">
              <div><p className="font-display text-3xl font-extrabold text-gradient">{stats.data?.pledges ?? 0}</p><p className="text-xs text-muted">{t("transplant.pledges", "donor pledges")}</p></div>
              <div><p className="font-display text-3xl font-extrabold text-gradient">{stats.data?.open_requests ?? 0}</p><p className="text-xs text-muted">{t("transplant.openRequests", "open requests")}</p></div>
              <div><p className="font-display text-3xl font-extrabold text-gradient">{stats.data?.by_organ?.heart ?? 0}</p><p className="text-xs text-muted">{t("transplant.heartPledges", "heart pledges")}</p></div>
            </div>
          )}
        </Card>
      </div>

      {!staff && (
        <Card>
          <div className="mb-3 flex items-center justify-between"><h2 className="text-lg font-bold">{t("transplant.myRequests", "My requests")}</h2><Link to="/hub/request/new" className="btn-soft">{t("transplant.newRequest", "New request")}</Link></div>
          {mine.isLoading ? <LoadingBlock rows={2} /> : !mine.data?.length ? (
            <EmptyState title={t("transplant.noRequests", "No requests yet")} body={t("transplant.noRequestsBody", "Create one to get a shareable message and public page.")} />
          ) : (
            <ul className="divide-y divide-[var(--border)]">
              {mine.data.map((r) => (
                <li key={r.id}><Link to={`/hub/request/${r.id}`} className="flex flex-wrap items-center gap-3 py-3 hover:opacity-90" data-testid="request-row">
                  <div className="min-w-0 flex-1"><p className="font-semibold">{r.patient_name} <span className="text-muted">· {r.blood_group}</span></p><p className="truncate text-sm text-muted">{r.hospital_name} · {fmtDate(r.created_at, i18n.language)}</p></div>
                  {r.verified && <Chip tone="ok">{t("transplant.verified", "Verified")}</Chip>}
                  <Chip tone={r.status === "open" ? "info" : r.status === "fulfilled" ? "ok" : "slate"}>{r.status}</Chip>
                  <span className="text-sm text-muted">{r.offers ?? 0} {t("transplant.offers", "offers")}</span>
                </Link></li>
              ))}
            </ul>
          )}
        </Card>
      )}
    </div>
  );
}
