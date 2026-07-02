import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        navy: {
          950: "#07111F",
          900: "#0B1B33",
        },
        gold: {
          500: "#C8A24A",
          400: "#E4C766",
        },
      },
      boxShadow: {
        premium: "0 24px 80px rgba(0, 0, 0, 0.32)",
      },
    },
  },
  plugins: [],
};

export default config;
