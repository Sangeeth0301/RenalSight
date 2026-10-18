import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import { PublicBar } from "@/components/Layout";

export default function NotFound() {
  const { t } = useTranslation();
  return (
    <div className="min-h-full bg-bg">
      <PublicBar />
      <main className="grid place-items-center px-4 py-24 text-center">
        <div><p className="text-7xl font-extrabold text-accent">404</p><p className="mt-3 text-xl font-semibold">{t("errors.notFound")}</p><Link to="/" className="btn-primary mt-6">{t("nav.home")}</Link></div>
      </main>
    </div>
  );
}
