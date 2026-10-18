import { Check } from "lucide-react";
import { useEffect } from "react";
import { useTranslation } from "react-i18next";
import { hasChosenLanguage, LANGS, setLanguage } from "@/i18n";
import { useSession } from "@/store/session";
import { Modal } from "./ui";
import { cn } from "@/lib/utils";

/** The language popup: opens on the very first visit and from the globe button. Instant, offline, no API key. */
export function LanguageDialog() {
  const { t, i18n } = useTranslation();
  const open = useSession((s) => s.langOpen);
  const setOpen = useSession((s) => s.setLangOpen);

  useEffect(() => { if (!hasChosenLanguage()) setOpen(true); }, [setOpen]);

  const choose = async (l: (typeof LANGS)[number]) => {
    await setLanguage(l);
    setOpen(false);
  };

  const close = () => {
    // closing without choosing still remembers English so the popup does not nag
    if (!hasChosenLanguage()) void setLanguage((i18n.language as any) || "en");
    setOpen(false);
  };

  return (
    <Modal open={open} onClose={close} title={t("lang.choose")}>
      <div className="grid gap-3 sm:grid-cols-2" data-testid="language-dialog">
        {LANGS.map((l) => (
          <button key={l} onClick={() => choose(l)} data-testid={`lang-${l}`}
            className={cn("flex min-h-[72px] items-center justify-between rounded-xl2 border-2 px-4 text-left text-xl font-semibold transition hover:shadow-soft",
              i18n.language === l ? "border-accent bg-accent-soft" : "border-line bg-white hover:border-accent")}>
            <span>{t(`lang.${l}`)}</span>
            {i18n.language === l && <Check className="h-6 w-6 text-accent" />}
          </button>
        ))}
      </div>
    </Modal>
  );
}
