import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        // Blue-navy scale (original identity, restored). navy-950 = page
        // background, 900 = surface, 800 = card/panel, 700 = elevated/border.
        navy: {
          950: "#07111F",
          900: "#0B1B33",
          800: "#12294A",
          700: "#1D3B63",
        },
        // Gold accent (original identity, restored). accent-500 for button
        // fills, accent-400 (lighter) for gold text on dark backgrounds.
        accent: {
          500: "#C8A24A",
          400: "#E4C766",
        },
        success: "#22C55E",
        destructive: "#EF4444",
      },
      fontFamily: {
        heading: ["Inter", "sans-serif"],
        sans: ["Inter", "sans-serif"],
        mono: ["Geist Mono", "monospace"],
      },
      boxShadow: {
        premium: "0 24px 80px rgba(0, 0, 0, 0.5)",
        glow: "0 0 3px rgba(200, 162, 74, 0.35), 0 2px 7px rgba(200, 162, 74, 0.25)",
      },
    },
  },
  plugins: [],
};

export default config;
