import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ["var(--font-sans)", "ui-sans-serif", "system-ui", "-apple-system", "Segoe UI", "Roboto", "sans-serif"],
        mono: ["var(--font-mono)", "ui-monospace", "SFMono-Regular", "Menlo", "Consolas", "monospace"],
      },
      colors: {
        surface: {
          DEFAULT: "rgba(255,255,255,0.03)",
          raised: "rgba(255,255,255,0.055)",
        },
      },
      boxShadow: {
        glow: "0 0 24px -6px rgba(99,102,241,0.45)",
        "glow-lg": "0 8px 40px -8px rgba(99,102,241,0.55)",
        card: "0 1px 0 0 rgba(255,255,255,0.04) inset, 0 8px 32px -12px rgba(0,0,0,0.6)",
      },
      animation: {
        "pulse-slow": "pulse 2.5s cubic-bezier(0.4, 0, 0.6, 1) infinite",
        "fade-up": "fade-up 0.55s cubic-bezier(0.16, 1, 0.3, 1) both",
        "fade-in": "fade-in 0.4s ease-out both",
        aurora: "aurora 22s ease-in-out infinite alternate",
        "aurora-slow": "aurora 34s ease-in-out infinite alternate-reverse",
        shimmer: "shimmer 2.4s linear infinite",
        "bounce-soft": "bounce-soft 1.6s ease-in-out infinite",
      },
      keyframes: {
        "fade-up": {
          "0%": { opacity: "0", transform: "translateY(10px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        "fade-in": {
          "0%": { opacity: "0" },
          "100%": { opacity: "1" },
        },
        aurora: {
          "0%": { transform: "translate(-8%, -4%) rotate(0deg) scale(1)" },
          "50%": { transform: "translate(6%, 8%) rotate(8deg) scale(1.12)" },
          "100%": { transform: "translate(-4%, 2%) rotate(-6deg) scale(1.04)" },
        },
        shimmer: {
          "0%": { backgroundPosition: "-200% 0" },
          "100%": { backgroundPosition: "200% 0" },
        },
        "bounce-soft": {
          "0%, 100%": { transform: "translateY(0)" },
          "50%": { transform: "translateY(-3px)" },
        },
      },
    },
  },
  plugins: [require("@tailwindcss/typography")],
};

export default config;
