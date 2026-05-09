import type { Config } from "tailwindcss";
import animate from "tailwindcss-animate";

const config: Config = {
  darkMode: ["class"],
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
    "./lib/**/*.{ts,tsx}",
    "./styles/**/*.{ts,tsx}",
    "./pages/**/*.{ts,tsx}"
  ],
  theme: {
    container: {
      center: true,
      padding: "2rem",
      screens: {
        "2xl": "1400px"
      }
    },
    extend: {
      fontFamily: {
        display: ["Manrope", "system-ui", "sans-serif"],
        sans: ["Inter", "system-ui", "sans-serif"],
        mono: ["JetBrains Mono", "ui-monospace", "SFMono-Regular", "monospace"]
      },
      colors: {
        background: "hsl(var(--surface-base-hsl))",
        foreground: "hsl(var(--text-primary-hsl))",
        muted: {
          DEFAULT: "hsl(var(--surface-muted-hsl))",
          foreground: "hsl(var(--text-muted-hsl))"
        },
        card: {
          DEFAULT: "hsl(var(--surface-card-hsl))",
          foreground: "hsl(var(--text-primary-hsl))"
        },
        border: "hsl(var(--border-strong-hsl))",
        input: "hsl(var(--border-soft-hsl))",
        ring: "hsl(var(--focus-ring-hsl))",
        primary: {
          DEFAULT: "hsl(var(--healthcare-primary-hsl))",
          foreground: "hsl(var(--surface-elevated-hsl))"
        },
        accent: {
          DEFAULT: "hsl(var(--healthcare-accent-hsl))",
          foreground: "hsl(var(--surface-elevated-hsl))"
        },
        warm: {
          DEFAULT: "hsl(var(--healthcare-warm-accent-hsl))",
          foreground: "hsl(var(--surface-elevated-hsl))"
        },
        success: {
          DEFAULT: "hsl(var(--success-hsl))",
          foreground: "hsl(var(--success-foreground-hsl))"
        },
        danger: {
          DEFAULT: "hsl(var(--danger-hsl))",
          foreground: "hsl(var(--surface-elevated-hsl))"
        }
      },
      borderRadius: {
        lg: "var(--radius-lg)",
        md: "var(--radius-md)",
        sm: "var(--radius-sm)"
      },
      boxShadow: {
        glass: "0 20px 40px -24px hsla(var(--healthcare-primary-hsl), 0.45)",
        hud: "0 10px 30px -18px hsla(var(--healthcare-accent-hsl), 0.35)"
      },
      spacing: {
        "2.5": "var(--space-xs)",
        4: "var(--space-sm)",
        6: "var(--space-md)",
        8: "var(--space-lg)",
        10: "var(--space-xl)"
      }
    }
  },
  plugins: [animate]
};

export default config;
