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
        // VERA brand (Catppuccin Blue Latte as reference; in dark it flips via CSS vars)
        vera: {
          50:  "#eef2ff",
          100: "#e0e7ff",
          200: "#c7d2fe",
          300: "#a5b4fc",
          400: "#818cf8",
          500: "#6366f1",
          600: "#4f46e5",
          700: "#1e66f5",  // Catppuccin Latte Blue (primary)
          800: "#1d4ed8",
          900: "#1e3a8a",
        },

        // Semantic tokens → CSS custom properties (RGB channel format)
        border:      "rgb(var(--border) / <alpha-value>)",
        input:       "rgb(var(--input) / <alpha-value>)",
        ring:        "rgb(var(--ring) / <alpha-value>)",
        background:  "rgb(var(--background) / <alpha-value>)",
        foreground:  "rgb(var(--foreground) / <alpha-value>)",
        primary: {
          DEFAULT:    "rgb(var(--primary) / <alpha-value>)",
          foreground: "rgb(var(--primary-foreground) / <alpha-value>)",
        },
        secondary: {
          DEFAULT:    "rgb(var(--secondary) / <alpha-value>)",
          foreground: "rgb(var(--secondary-foreground) / <alpha-value>)",
        },
        destructive: {
          DEFAULT:    "rgb(var(--destructive) / <alpha-value>)",
          foreground: "rgb(var(--destructive-foreground) / <alpha-value>)",
        },
        muted: {
          DEFAULT:    "rgb(var(--muted) / <alpha-value>)",
          foreground: "rgb(var(--muted-foreground) / <alpha-value>)",
        },
        accent: {
          DEFAULT:    "rgb(var(--accent) / <alpha-value>)",
          foreground: "rgb(var(--accent-foreground) / <alpha-value>)",
        },
        card: {
          DEFAULT:    "rgb(var(--card) / <alpha-value>)",
          foreground: "rgb(var(--card-foreground) / <alpha-value>)",
        },

        // Catppuccin palette tokens (for arbitrary use in JSX)
        ctp: {
          rosewater: "rgb(var(--ctp-rosewater) / <alpha-value>)",
          flamingo:  "rgb(var(--ctp-flamingo) / <alpha-value>)",
          pink:      "rgb(var(--ctp-pink) / <alpha-value>)",
          mauve:     "rgb(var(--ctp-mauve) / <alpha-value>)",
          red:       "rgb(var(--ctp-red) / <alpha-value>)",
          maroon:    "rgb(var(--ctp-maroon) / <alpha-value>)",
          peach:     "rgb(var(--ctp-peach) / <alpha-value>)",
          yellow:    "rgb(var(--ctp-yellow) / <alpha-value>)",
          green:     "rgb(var(--ctp-green) / <alpha-value>)",
          teal:      "rgb(var(--ctp-teal) / <alpha-value>)",
          sky:       "rgb(var(--ctp-sky) / <alpha-value>)",
          sapphire:  "rgb(var(--ctp-sapphire) / <alpha-value>)",
          blue:      "rgb(var(--ctp-blue) / <alpha-value>)",
          lavender:  "rgb(var(--ctp-lavender) / <alpha-value>)",
          text:      "rgb(var(--ctp-text) / <alpha-value>)",
          subtext1:  "rgb(var(--ctp-subtext1) / <alpha-value>)",
          subtext0:  "rgb(var(--ctp-subtext0) / <alpha-value>)",
          overlay2:  "rgb(var(--ctp-overlay2) / <alpha-value>)",
          overlay1:  "rgb(var(--ctp-overlay1) / <alpha-value>)",
          overlay0:  "rgb(var(--ctp-overlay0) / <alpha-value>)",
          surface2:  "rgb(var(--ctp-surface2) / <alpha-value>)",
          surface1:  "rgb(var(--ctp-surface1) / <alpha-value>)",
          surface0:  "rgb(var(--ctp-surface0) / <alpha-value>)",
          base:      "rgb(var(--ctp-base) / <alpha-value>)",
          mantle:    "rgb(var(--ctp-mantle) / <alpha-value>)",
          crust:     "rgb(var(--ctp-crust) / <alpha-value>)",
        },
      },
      borderRadius: {
        lg: "var(--radius)",
        md: "calc(var(--radius) - 2px)",
        sm: "calc(var(--radius) - 4px)",
      },
    },
  },
  plugins: [],
};

export default config;
