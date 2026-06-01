/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
        mono: ["JetBrains Mono", "Fira Code", "monospace"],
      },
      colors: {
        bg:      "#0A0A0F",
        surface: "#111118",
        card:    "#16161F",
        border:  "#1E1E2E",
        accent:  "#6C63FF",
        accent2: "#4F46E5",
        success: "#10B981",
        warning: "#F59E0B",
        danger:  "#EF4444",
        muted:   "#4A4A6A",
        text:    "#E2E2F0",
        subtext: "#6B6B8A",
      },
      animation: {
        "fade-in":    "fadeIn 0.3s ease",
        "slide-up":   "slideUp 0.3s ease",
        "pulse-slow": "pulse 3s ease-in-out infinite",
        "shimmer":    "shimmer 2s linear infinite",
      },
      keyframes: {
        fadeIn:  { from: { opacity: 0 }, to: { opacity: 1 } },
        slideUp: { from: { opacity: 0, transform: "translateY(8px)" },
                   to:   { opacity: 1, transform: "translateY(0)" } },
        shimmer: { from: { backgroundPosition: "-200% 0" },
                   to:   { backgroundPosition: "200% 0" } },
      },
      boxShadow: {
        card:    "0 0 0 1px rgba(108,99,255,0.08), 0 4px 24px rgba(0,0,0,0.4)",
        glow:    "0 0 20px rgba(108,99,255,0.3)",
        "glow-sm":"0 0 10px rgba(108,99,255,0.2)",
      },
    },
  },
  plugins: [],
}
