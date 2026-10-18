import { lazy, Suspense, useEffect, type ReactNode } from "react";
import { Navigate, Outlet, Route, Routes, useLocation } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Layout, PublicBar } from "@/components/Layout";
import { LanguageDialog } from "@/components/LanguageDialog";
import { ErrorBoundary } from "@/components/ErrorBoundary";
import { LoadingBlock, Spinner, Toasts } from "@/components/ui";
import type { Role } from "@/lib/api";
import { homeFor } from "@/lib/hooks";
import { useSession } from "@/store/session";
import Landing from "@/pages/Landing";
import { Login, Register } from "@/pages/Auth";
import Onboarding from "@/pages/Onboarding";

const Home = lazy(() => import("@/pages/Home"));
const Reports = lazy(() => import("@/pages/Reports"));
const KidneyPage = lazy(() => import("@/pages/KidneyPage"));
const KidneyDemo = lazy(() => import("@/pages/KidneyDemo"));
const Forecast = lazy(() => import("@/pages/Forecast"));
const Care = lazy(() => import("@/pages/Care"));
const Rx = lazy(() => import("@/pages/Rx"));
const Chat = lazy(() => import("@/pages/Chat"));
const Rooms = lazy(() => import("@/pages/Rooms"));
const Buddy = lazy(() => import("@/pages/Buddy"));
const Pulse = lazy(() => import("@/pages/Pulse"));
const Notifications = lazy(() => import("@/pages/Notifications"));
const Settings = lazy(() => import("@/pages/Settings"));
const DoctorHome = lazy(() => import("@/pages/DoctorHome"));
const DoctorPatient = lazy(() => import("@/pages/DoctorPatient"));
const DoctorQueue = lazy(() => import("@/pages/DoctorQueue"));
const DoctorRx = lazy(() => import("@/pages/DoctorRx"));
const DoctorSchedule = lazy(() => import("@/pages/DoctorSchedule"));
const Admin = lazy(() => import("@/pages/Admin"));
const Rituals = lazy(() => import("@/pages/Rituals"));
const Community = lazy(() => import("@/pages/Community"));
const CareHub = lazy(() => import("@/pages/CareHub"));
const Offline = lazy(() => import("@/pages/Offline"));
const Research = lazy(() => import("@/pages/Research"));
const Inbox = lazy(() => import("@/pages/Inbox"));
const Hub = lazy(() => import("@/pages/hub/Hub"));
const RequestNew = lazy(() => import("@/pages/hub/RequestNew"));
const RequestDetail = lazy(() => import("@/pages/hub/RequestDetail"));
const PublicRequest = lazy(() => import("@/pages/hub/PublicRequest"));
const Donate = lazy(() => import("@/pages/hub/Donate"));
const Hospitals = lazy(() => import("@/pages/hub/Hospitals"));
const Journey = lazy(() => import("@/pages/hub/Journey"));
const Dialysis = lazy(() => import("@/pages/hub/Dialysis"));
const IdCardPage = lazy(() => import("@/pages/hub/IdCardPage"));
const PublicId = lazy(() => import("@/pages/hub/IdCardPage").then((m) => ({ default: m.PublicId })));
const Broadcast = lazy(() => import("@/pages/hub/Broadcast"));
const Desk = lazy(() => import("@/pages/hub/Desk"));
const NotFound = lazy(() => import("@/pages/NotFound"));

function RequireAuth() {
  const { user, ready } = useSession();
  const loc = useLocation();
  if (!ready) return <div className="grid h-full place-items-center"><Spinner className="h-8 w-8" /></div>;
  if (!user) return <Navigate to="/login" replace state={{ from: loc.pathname }} />;
  return <Outlet />;
}

/** Pages that anyone can open: signed-in users get the app shell, visitors get a simple top bar. */
function MaybeLayout() {
  const { user, ready } = useSession();
  if (!ready) return <div className="grid h-full place-items-center"><Spinner className="h-8 w-8" /></div>;
  if (user) return <Layout />;
  return (
    <div className="min-h-full bg-bg" style={{ "--stick": "4rem" } as React.CSSProperties}>
      <PublicBar />
      <main className="mx-auto max-w-[1200px] px-4 py-6 sm:px-6"><Outlet /></main>
      <Toasts />
    </div>
  );
}

function RequireRole({ roles, children }: { roles: Role[]; children: ReactNode }) {
  const user = useSession((s) => s.user)!;
  if (!roles.includes(user.role)) return <Navigate to={homeFor(user.role)} replace />;
  return <>{children}</>;
}

const P: Role[] = ["patient"];
const PC: Role[] = ["patient", "caregiver"];
const D: Role[] = ["doctor"];
const ALL: Role[] = ["patient", "caregiver", "doctor", "admin"];

export default function App() {
  const init = useSession((s) => s.init);
  const { i18n } = useTranslation();
  useEffect(() => { void init(); }, [init]);
  useEffect(() => { document.documentElement.lang = i18n.language; }, [i18n.language]);
  const wrap = (el: ReactNode, roles: Role[] = ALL) => (
    <RequireRole roles={roles}><Suspense fallback={<LoadingBlock />}>{el}</Suspense></RequireRole>
  );

  return (
    <ErrorBoundary>
      <LanguageDialog />
      <Routes>
        <Route path="/" element={<Landing />} />
        <Route path="/login" element={<Login />} />
        <Route path="/register" element={<Register />} />
        <Route path="/kidney/demo" element={<Suspense fallback={<LoadingBlock />}><KidneyDemo /></Suspense>} />
        <Route path="/r/:token" element={<Suspense fallback={<LoadingBlock />}><PublicRequest /></Suspense>} />
        <Route path="/e/:token" element={<Suspense fallback={<LoadingBlock />}><PublicId /></Suspense>} />
        <Route element={<MaybeLayout />}>
          <Route path="/pulse" element={<Suspense fallback={<LoadingBlock />}><Pulse /></Suspense>} />
        </Route>
        <Route element={<RequireAuth />}>
          <Route path="/onboarding" element={<Onboarding />} />
          <Route element={<Layout />}>
            <Route path="/home" element={wrap(<Home />, PC)} />
            <Route path="/reports" element={wrap(<Reports />, P)} />
            <Route path="/kidney" element={wrap(<KidneyPage />, PC)} />
            <Route path="/forecast" element={wrap(<Forecast />, P)} />
            <Route path="/care" element={wrap(<Care />, P)} />
            <Route path="/rx" element={wrap(<Rx />, P)} />
            <Route path="/chat" element={wrap(<Chat />)} />
            <Route path="/chat/:threadId" element={wrap(<Chat />)} />
            <Route path="/rooms" element={wrap(<Rooms />)} />
            <Route path="/rooms/:id" element={wrap(<Rooms />)} />
            <Route path="/buddy" element={wrap(<Buddy />, PC)} />
            <Route path="/notifications" element={wrap(<Notifications />)} />
            <Route path="/settings" element={wrap(<Settings />)} />
            <Route path="/doctor" element={wrap(<DoctorHome />, D)} />
            <Route path="/doctor/schedule" element={wrap(<DoctorSchedule />, D)} />
            <Route path="/doctor/queue" element={wrap(<DoctorQueue />, D)} />
            <Route path="/doctor/patients/:id" element={wrap(<DoctorPatient />, D)} />
            <Route path="/doctor/rx/:id" element={wrap(<DoctorRx />, D)} />
            <Route path="/admin" element={wrap(<Admin />, ["admin"])} />
            <Route path="/rituals" element={wrap(<Rituals />, P)} />
            <Route path="/community" element={wrap(<Community />)} />
            <Route path="/care-hub" element={wrap(<CareHub />, PC)} />
            <Route path="/offline" element={wrap(<Offline />, PC)} />
            <Route path="/research" element={wrap(<Research />)} />
            <Route path="/hub" element={wrap(<Hub />)} />
            <Route path="/hub/request/new" element={wrap(<RequestNew />, PC)} />
            <Route path="/hub/request/:id" element={wrap(<RequestDetail />)} />
            <Route path="/hub/donate" element={wrap(<Donate />)} />
            <Route path="/hub/hospitals" element={wrap(<Hospitals />)} />
            <Route path="/hub/journey" element={wrap(<Journey />, PC)} />
            <Route path="/hub/dialysis" element={wrap(<Dialysis />, PC)} />
            <Route path="/hub/id" element={wrap(<IdCardPage />)} />
            <Route path="/hub/broadcast" element={wrap(<Broadcast />)} />
            <Route path="/hub/desk" element={wrap(<Desk />, ["doctor", "admin"])} />
            <Route path="/inbox" element={wrap(<Inbox />, ["patient", "doctor", "admin"])} />
          </Route>
        </Route>
        <Route path="*" element={<Suspense fallback={null}><NotFound /></Suspense>} />
      </Routes>
    </ErrorBoundary>
  );
}
