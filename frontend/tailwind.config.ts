import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ["var(--font-sans)", "system-ui", "sans-serif"],
        mono: ["var(--font-mono)", "ui-monospace", "monospace"],
      },
      colors: {
        // Flat neutral scale — no brand color. Color is reserved entirely for
        // the four decision states below; nothing else in the UI is tinted.
        canvas: "#0a0a0b",
        panel: "#141416",
        line: "#26262a",
        ink: "#f2f2f3",
        muted: "#8b8b92",
        faint: "#5a5a60",
        // Decision states — the only color in the interface, used only where
        // it means something.
        allow: "#3fb950",
        block: "#f85149",
        clarify: "#d29922",
        review: "#8b7fe8",
      },
    },
  },
  plugins: [],
};

export default config;
