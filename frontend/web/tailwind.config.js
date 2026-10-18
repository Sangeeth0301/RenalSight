/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: "var(--bg)", card: "var(--card)", ink: "var(--ink)", muted: "var(--muted)", line: "var(--border)",
        primary: "var(--primary)", "primary-soft": "var(--primary-soft)", accent: "var(--accent)", "accent-soft": "var(--accent-soft)",
        ok: "var(--ok)", warn: "var(--warn)", danger: "var(--danger)", info: "var(--info)",
      },
      borderRadius: { xl2: "16px", xl3: "24px" },
      boxShadow: { soft: "0 1px 2px rgba(15,23,42,.04), 0 8px 24px rgba(15,23,42,.06)", lift: "0 2px 4px rgba(15,23,42,.06), 0 16px 36px rgba(15,23,42,.10)" },
      fontFamily: { display: ["Sora", "Inter", "system-ui", "sans-serif"], sans: ["Inter", "Noto Sans Tamil", "Noto Sans Bengali", "Noto Sans Telugu", "system-ui", "sans-serif"] },
      keyframes: {
        pulseSoft: { "0%,100%": { transform: "scale(1)" }, "50%": { transform: "scale(1.03)" } },
        drip: { "0%": { transform: "translateY(0)", opacity: "0.9" }, "100%": { transform: "translateY(26px)", opacity: "0" } },
        shake: { "0%,100%": { transform: "translateX(0)" }, "25%": { transform: "translateX(-2px)" }, "75%": { transform: "translateX(2px)" } },
        irregular: { "0%,100%": { transform: "scale(1)" }, "8%": { transform: "scale(1.045)" }, "16%": { transform: "scale(.99)" }, "52%": { transform: "scale(1.02)" }, "60%": { transform: "scale(1)" } },
        ecg: { "0%": { strokeDashoffset: "200" }, "100%": { strokeDashoffset: "0" } },
        fadeUp: { "0%": { opacity: "0", transform: "translateY(10px)" }, "100%": { opacity: "1", transform: "translateY(0)" } },
      },
      animation: { pulseSoft: "pulseSoft 2.2s ease-in-out infinite", drip: "drip 1.6s ease-in infinite", shake: "shake .5s ease-in-out infinite", irregular: "irregular 1.7s ease-in-out infinite", slowPulse: "pulseSoft 3.4s ease-in-out infinite", ecg: "ecg 1.6s linear infinite", fadeUp: "fadeUp .35s ease-out both" },
    },
  },
  plugins: [],
};
