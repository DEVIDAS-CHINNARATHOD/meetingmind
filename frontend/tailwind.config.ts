import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: ["class"],
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        // MeetingMind design system
        background:  "hsl(var(--background))",
        foreground:  "hsl(var(--foreground))",
        card:        { DEFAULT: "hsl(var(--card))",       foreground: "hsl(var(--card-foreground))" },
        popover:     { DEFAULT: "hsl(var(--popover))",    foreground: "hsl(var(--popover-foreground))" },
        primary:     { DEFAULT: "hsl(var(--primary))",    foreground: "hsl(var(--primary-foreground))" },
        secondary:   { DEFAULT: "hsl(var(--secondary))",  foreground: "hsl(var(--secondary-foreground))" },
        muted:       { DEFAULT: "hsl(var(--muted))",      foreground: "hsl(var(--muted-foreground))" },
        accent:      { DEFAULT: "hsl(var(--accent))",     foreground: "hsl(var(--accent-foreground))" },
        destructive: { DEFAULT: "hsl(var(--destructive))", foreground: "hsl(var(--destructive-foreground))" },
        border:      "hsl(var(--border))",
        input:       "hsl(var(--input))",
        ring:        "hsl(var(--ring))",
        // Brand tokens
        violet: {
          50:  "#f5f3ff", 100: "#ede9fe", 200: "#ddd6fe",
          300: "#c4b5fd", 400: "#a78bfa", 500: "#8b5cf6",
          600: "#7c3aed", 700: "#6d28d9", 800: "#5b21b6",
          900: "#4c1d95", 950: "#2e1065",
        },
        ink: {
          50:  "#f0f0f8", 100: "#e0e0f0", 200: "#c4c4e4",
          300: "#9898cc", 400: "#6c6caa", 500: "#4a4a8a",
          600: "#363672", 700: "#252560", 800: "#15153a",
          900: "#0d0d26", 950: "#07071a",
        },
      },
      fontFamily: {
        display: ["var(--font-syne)", "system-ui", "sans-serif"],
        body:    ["var(--font-dm-sans)", "system-ui", "sans-serif"],
        mono:    ["var(--font-jetbrains)", "monospace"],
      },
      borderRadius: {
        lg: "var(--radius)",
        md: "calc(var(--radius) - 2px)",
        sm: "calc(var(--radius) - 4px)",
      },
      keyframes: {
        "fade-in":     { from: { opacity: "0", transform: "translateY(8px)" }, to: { opacity: "1", transform: "translateY(0)" } },
        "fade-out":    { from: { opacity: "1" }, to: { opacity: "0" } },
        "slide-in-r":  { from: { transform: "translateX(100%)" }, to: { transform: "translateX(0)" } },
        "scale-in":    { from: { opacity: "0", transform: "scale(0.95)" }, to: { opacity: "1", transform: "scale(1)" } },
        "wave":        { "0%,100%": { transform: "scaleY(0.4)" }, "50%": { transform: "scaleY(1)" } },
        "pulse-dot":   { "0%,100%": { transform: "scale(1)", opacity: "1" }, "50%": { transform: "scale(1.4)", opacity: "0.6" } },
        "shimmer":     { "0%": { backgroundPosition: "-400px 0" }, "100%": { backgroundPosition: "400px 0" } },
        "float":       { "0%,100%": { transform: "translateY(0px)" }, "50%": { transform: "translateY(-6px)" } },
        "spin-slow":   { from: { transform: "rotate(0deg)" }, to: { transform: "rotate(360deg)" } },
      },
      animation: {
        "fade-in":   "fade-in 0.35s ease forwards",
        "scale-in":  "scale-in 0.25s ease forwards",
        "slide-in-r":"slide-in-r 0.3s cubic-bezier(0.16,1,0.3,1)",
        "wave":      "wave 1.4s ease-in-out infinite",
        "pulse-dot": "pulse-dot 1.2s ease-in-out infinite",
        "shimmer":   "shimmer 1.6s linear infinite",
        "float":     "float 3s ease-in-out infinite",
        "spin-slow": "spin-slow 8s linear infinite",
      },
      backgroundImage: {
        "gradient-radial":  "radial-gradient(var(--tw-gradient-stops))",
        "gradient-conic":   "conic-gradient(from 180deg at 50% 50%, var(--tw-gradient-stops))",
        "mesh-violet":      "radial-gradient(at 40% 20%, hsla(265,90%,60%,0.2) 0px, transparent 50%), radial-gradient(at 80% 0%, hsla(250,80%,50%,0.15) 0px, transparent 50%), radial-gradient(at 0% 50%, hsla(280,85%,55%,0.1) 0px, transparent 50%)",
      },
    },
  },
  plugins: [],
};

export default config;
