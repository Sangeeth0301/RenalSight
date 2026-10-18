import * as Popover from "@radix-ui/react-popover";
import { AnimatePresence, motion } from "framer-motion";
import { useEffect, useId, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import type { KidneyState, Wound } from "@/lib/api";
import { cn, fmtNumber } from "@/lib/utils";

// Same bean-shaped outline as the design document.
const BODY = "M 92.0 72.5 C 172.0 68.6 176.0 219.8 96.0 227.5 C 32.0 227.5 52.0 173.2 88.0 150.0 C 52.0 126.8 32.0 72.5 92.0 72.5 Z";
const CRACKS = [
  "M 120 103.5 L 128 119 L 124 124 L 136 134.5", "M 112 173.2 L 124 186 L 120 191 L 136 204.2", "M 136 142.2 L 126 150 L 128 156 L 116 165.5",
  "M 108 88 L 118 104 L 114 110 L 128 122.9", "M 132 188.8 L 122 200 L 124 206 L 112 219.8", "M 124 126.8 L 136 134 L 134 141 L 148 150",
  "M 104 157.8 L 112 170 L 116 174 L 124 188.8", "M 144 95.8 L 138 110 L 140 116 L 132 126.8", "M 120 212 L 132 196 L 128 190 L 140 181",
];
const VEINS = ["M 72 92 C 92 108 112 100 132 124", "M 66 150 C 90 148 108 160 130 180", "M 78 205 C 96 196 112 200 134 214"];
const LOOK: Record<number, { fill: string; edge: string; bg: string }> = {
  1: { fill: "#fb7185", edge: "#9f1239", bg: "var(--kb1)" },
  2: { fill: "#e56b7d", edge: "#881337", bg: "var(--kb2)" },
  3: { fill: "#c4707a", edge: "#6b1d2c", bg: "var(--kb3)" },
  4: { fill: "#9c7469", edge: "#4a2a2a", bg: "var(--kb4)" },
  5: { fill: "#6b7280", edge: "#1f2937", bg: "var(--kb5)" },
};
export const stageLook = (stage: number) => LOOK[Math.max(1, Math.min(5, stage))];

const UNIT: Record<Wound["code"], string> = { cracks: "mL/min", leak: "mg/g", veins: "mmHg", pallor: "g/dL", flicker: "mmol/L" };
// Hotspot positions (percent of the kidney box)
const SPOT: Record<Wound["code"], { x: number; y: number }> = { cracks: { x: 128, y: 142 }, leak: { x: 92, y: 220 }, veins: { x: 112, y: 104 }, pallor: { x: 70, y: 132 }, flicker: { x: 138, y: 92 } };

function EcgLine({ pulse, danger }: { pulse: KidneyState["pulse"]; danger: boolean }) {
  const flat = pulse === "flatline";
  const d = flat ? "M0 12 L100 12" : pulse === "irregular"
    ? "M0 12 L14 12 L18 4 L22 20 L26 12 L38 12 L44 12 L47 2 L52 22 L56 12 L80 12 L84 7 L88 17 L92 12 L100 12"
    : "M0 12 L20 12 L25 3 L30 21 L35 12 L60 12 L65 3 L70 21 L75 12 L100 12";
  return (
    <svg viewBox="0 0 100 24" className="h-6 w-full" aria-hidden>
      <path d={d} fill="none" stroke={danger || flat ? "#e11d48" : "#10b981"} strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" strokeDasharray={flat ? undefined : "200"} className={flat ? "" : "animate-ecg"} />
    </svg>
  );
}

export function LivingKidney({ state, size = "md", interactive = false, showEcg = true, className }: { state: KidneyState; size?: "sm" | "md" | "lg"; interactive?: boolean; showEcg?: boolean; className?: string }) {
  const { t, i18n } = useTranslation();
  const uid = useId().replace(/:/g, "");
  const look = stageLook(state.visual_stage);
  const wound = (code: Wound["code"]) => state.wounds.find((w) => w.code === code);
  const cracks = wound("cracks"), leak = wound("leak"), veins = wound("veins"), pallor = wound("pallor"), flicker = wound("flicker");
  const nCracks = Math.round((cracks?.level ?? 0) * 9) + (state.visual_stage >= 4 ? 1 : 0);
  const nDrops = Math.ceil((leak?.level ?? 0) * 5);
  const sizes = { sm: "w-28", md: "w-48 sm:w-56", lg: "w-60 sm:w-72" } as const;

  // heal / worsen feedback
  const prev = useRef<number | null>(null);
  const [mood, setMood] = useState<"heal" | "worse" | null>(null);
  useEffect(() => {
    if (prev.current !== null && prev.current !== state.severity) {
      setMood(state.severity < prev.current ? "heal" : "worse");
      const id = setTimeout(() => setMood(null), 1800);
      prev.current = state.severity;
      return () => clearTimeout(id);
    }
    prev.current = state.severity;
  }, [state.severity]);

  const pulseClass = useMemo(() => {
    switch (state.pulse) {
      case "calm": return "animate-pulseSoft";
      case "slow": return "animate-slowPulse";
      case "irregular": return "animate-irregular";
      default: return "";
    }
  }, [state.pulse]);
  const stage = state.visual_stage;
  const pieces = stage === 5 ? [[150, 120, 7], [66, 190, 6], [138, 214, 8], [104, 90, 5]] : [];

  const spots = (interactive ? state.wounds.filter((w) => w.level > 0) : []);
  const sr = `${t(`stages.${state.stage_name}`)}, ${t("kidney.severity")} ${Math.round(state.severity)}%`;

  return (
    <div className={cn("relative mx-auto select-none", sizes[size], className)}>
      <div className={cn("relative rounded-xl3 p-2 transition-colors duration-700", mood === "worse" && "animate-shake")} style={{ background: look.bg }}>
        <div className="relative aspect-[2/3] w-full">
          <div className={cn("h-full w-full", pulseClass, stage === 4 && "animate-shake")} style={{ animationDuration: stage === 4 ? "1.1s" : undefined }}>
          <svg viewBox="0 0 200 300" className="h-full w-full overflow-visible" role="img" aria-label={sr}>
            <defs>
              <radialGradient id={`g${uid}`} cx="38%" cy="32%" r="75%">
                <stop offset="0%" stopColor="#fff" stopOpacity={stage === 1 ? 0.55 : 0.2} />
                <stop offset="38%" stopColor={look.fill} />
                <stop offset="100%" stopColor={look.edge} stopOpacity="0.85" />
              </radialGradient>
              <clipPath id={`c${uid}`}><path d={BODY} /></clipPath>
              {stage === 4 && <filter id={`glow${uid}`}><feDropShadow dx="0" dy="0" stdDeviation="5" floodColor="#e11d48" floodOpacity="0.45" /></filter>}
            </defs>
            <g style={{ transformOrigin: "100px 150px", transform: `scale(${state.shrink})`, transition: "transform 1.2s ease" }} filter={stage === 4 ? `url(#glow${uid})` : undefined}>
              <path d={BODY} fill={`url(#g${uid})`} stroke={look.edge} strokeWidth="3" strokeLinejoin="round" />
              <g clipPath={`url(#c${uid})`}>
                {/* pallor */}
                <rect x="0" y="0" width="200" height="300" fill="#fff" opacity={(pallor?.level ?? 0) * 0.55} style={{ transition: "opacity 1.2s" }} />
                {/* stressed patches / scars */}
                {stage >= 2 && <ellipse cx="128" cy="112" rx="13" ry="9" fill="#000" opacity={0.08 + stage * 0.02} />}
                {stage >= 2 && <ellipse cx="108" cy="190" rx="10" ry="12" fill="#000" opacity={0.07 + stage * 0.02} />}
                {stage >= 3 && <path d="M 60 110 L 76 126 M 70 170 L 88 178" stroke="#3b0a14" strokeWidth="3" strokeLinecap="round" opacity="0.5" />}
                {/* veins */}
                {(veins?.level ?? 0) > 0.08 && VEINS.map((d, i) => (
                  <path key={i} d={d} fill="none" stroke="#be123c" strokeWidth={1.4 + (veins!.level) * 3.2} strokeLinecap="round" opacity={0.35 + veins!.level * 0.5} />
                ))}
                {/* cracks */}
                <AnimatePresence>
                  {CRACKS.slice(0, Math.min(nCracks, 9)).map((d, i) => (
                    <motion.path key={d} d={d} fill="none" stroke="#1f0a0a" strokeWidth={stage >= 4 ? 3 : 2} strokeLinecap="round" strokeLinejoin="round"
                      initial={{ pathLength: 0, opacity: 0 }} animate={{ pathLength: 1, opacity: 1 }} exit={{ pathLength: 0, opacity: 0 }} transition={{ duration: 0.7, delay: i * 0.06 }} />
                  ))}
                </AnimatePresence>
                {/* soft highlight */}
                {stage <= 2 && <ellipse cx="78" cy="96" rx="22" ry="11" fill="#fff" opacity="0.28" transform="rotate(-25 78 96)" />}
              </g>
              {/* leaking drops */}
              {Array.from({ length: nDrops }).map((_, i) => (
                <circle key={i} cx={60 + i * 14} cy={218 + (i % 2) * 6} r="3.4" fill="#93c5fd" stroke="#2563eb" strokeWidth="0.8" className="animate-drip" style={{ animationDelay: `${i * 0.35}s` }} />
              ))}
              {/* bleeding at stage 4+ */}
              {stage >= 4 && [0, 1, 2].map((i) => (
                <ellipse key={i} cx={100 + i * 16} cy={226} rx="2.4" ry="4" fill="#be123c" className="animate-drip" style={{ animationDelay: `${i * 0.5}s` }} />
              ))}
              {/* crumbling pieces */}
              {pieces.map(([x, y, r], i) => (
                <motion.polygon key={i} points={`${x},${y - r} ${x + r},${y + r * 0.6} ${x - r * 0.8},${y + r}`} fill={look.fill} stroke={look.edge} strokeWidth="1.5"
                  animate={{ y: [0, 22, 40], x: [0, (i % 2 ? 10 : -10), (i % 2 ? 18 : -18)], rotate: [0, 40, 90], opacity: [0.95, 0.7, 0] }}
                  transition={{ duration: 3.6, repeat: Infinity, delay: i * 0.7, ease: "easeIn" }} />
              ))}
            </g>
          </svg>
          </div>
          {/* heal confetti */}
          <AnimatePresence>
            {mood === "heal" && (
              <motion.div className="pointer-events-none absolute inset-0 grid place-items-center text-4xl" initial={{ opacity: 0, scale: 0.6 }} animate={{ opacity: 1, scale: 1.15 }} exit={{ opacity: 0 }}>✨</motion.div>
            )}
          </AnimatePresence>
          {/* hotspots */}
          {spots.map((w) => (
            <Popover.Root key={w.code}>
              <Popover.Trigger asChild>
                <button aria-label={t(`wounds.${w.code}.title`)} className="absolute grid h-11 w-11 -translate-x-1/2 -translate-y-1/2 place-items-center rounded-full"
                  style={{ left: `${((100 + (SPOT[w.code].x - 100) * state.shrink) / 200) * 100}%`, top: `${((150 + (SPOT[w.code].y - 150) * state.shrink) / 300) * 100}%` }}>
                  <span className="h-4 w-4 animate-ping rounded-full bg-white/80 ring-2 ring-danger/70" />
                  <span className="absolute h-3.5 w-3.5 rounded-full bg-white ring-2 ring-danger" />
                </button>
              </Popover.Trigger>
              <Popover.Portal>
                <Popover.Content sideOffset={8} className="card z-[80] w-72 p-4 shadow-lift">
                  <p className="font-semibold">{t(`wounds.${w.code}.title`)}</p>
                  {w.value !== null && w.value !== undefined && (
                    <p className="mt-0.5 text-sm text-muted">{fmtNumber(w.value, i18n.language)} {UNIT[w.code]}</p>
                  )}
                  <p className="mt-2 text-sm">{t(`wounds.${w.code}.cause`)}</p>
                  <p className="mt-2 rounded-lg bg-accent-soft p-2 text-sm">{t(`wounds.${w.code}.tip`)}</p>
                  <Popover.Arrow className="fill-white" />
                </Popover.Content>
              </Popover.Portal>
            </Popover.Root>
          ))}
        </div>
        {showEcg && size !== "sm" && <EcgLine pulse={state.pulse} danger={(flicker?.level ?? 0) > 0.3 || stage >= 4} />}
      </div>
    </div>
  );
}

/** Tiny kidney for the top bar, cards and chat attachments (no popovers). */
export function MiniKidney({ state, size = 28, className }: { state: Pick<KidneyState, "visual_stage" | "shrink" | "has_data"> | null | undefined; size?: number; className?: string }) {
  const stage = state?.has_data ? state.visual_stage : 1;
  const look = stageLook(stage);
  const scale = state?.has_data ? state.shrink : 1;
  return (
    <svg width={size} height={size * 1.4} viewBox="30 60 150 185" className={className} aria-hidden>
      <g style={{ transformOrigin: "100px 150px", transform: `scale(${scale})` }}>
        <path d={BODY} fill={look.fill} stroke={look.edge} strokeWidth="9" strokeLinejoin="round" />
        {stage >= 3 && <path d={CRACKS[0]} stroke="#1f0a0a" strokeWidth="8" fill="none" strokeLinecap="round" />}
        {stage >= 4 && <path d={CRACKS[1]} stroke="#1f0a0a" strokeWidth="8" fill="none" strokeLinecap="round" />}
        {stage === 5 && <path d={CRACKS[3]} stroke="#1f0a0a" strokeWidth="8" fill="none" strokeLinecap="round" />}
      </g>
    </svg>
  );
}

export const NO_STATE: KidneyState = {
  has_data: true, g_stage: "G1", a_category: null, visual_stage: 1, stage_name: "healthy", severity: 0, theme: "healthy", shrink: 1, pulse: "calm", wounds: [], urgent: false,
};
