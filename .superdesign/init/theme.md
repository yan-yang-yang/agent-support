# Theme

## Compact token summary

- Canvas/background: `#f4f7f9` (`--background: 203 29% 97%`)
- Foreground: `#17212b` (`--foreground: 210 30% 13%`)
- Primary blue: `#2f80ed` (`--primary: 214 83% 56%`)
- Muted: `#f4f7f9`; muted foreground `#6f7c88`
- Border/input: `#e5ebf0` (`207 25% 92%`)
- Success: `#16866e`; warning: `#e79a2d`; soft blue: `#eaf4ff`
- Font stack: Inter, PingFang SC, Microsoft YaHei, system sans-serif
- Base radius: `0.9rem`; business cards use 20px; composer uses 22px
- Soft shadow: `0 10px 30px rgba(31, 65, 94, 0.08)`
- Mobile target width: 375–430px; desktop preview keeps a 430px device shell
- Motion: 180ms message entry, 1s cursor pulse, reduced-motion override

## Raw `apps/web/tailwind.config.ts`

```ts
import type { Config } from "tailwindcss"
import animate from "tailwindcss-animate"

export default {
  darkMode: ["class"],
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        border: "hsl(var(--border))",
        input: "hsl(var(--input))",
        ring: "hsl(var(--ring))",
        background: "hsl(var(--background))",
        foreground: "hsl(var(--foreground))",
        primary: {
          DEFAULT: "hsl(var(--primary))",
          foreground: "hsl(var(--primary-foreground))",
        },
        muted: {
          DEFAULT: "hsl(var(--muted))",
          foreground: "hsl(var(--muted-foreground))",
        },
      },
      borderRadius: {
        lg: "var(--radius)",
        md: "calc(var(--radius) - 2px)",
        sm: "calc(var(--radius) - 4px)",
      },
      boxShadow: {
        soft: "0 10px 30px rgba(31, 65, 94, 0.08)",
      },
      keyframes: {
        "message-in": {
          from: { opacity: "0", transform: "translateY(6px)" },
          to: { opacity: "1", transform: "translateY(0)" },
        },
        cursor: {
          "0%, 100%": { opacity: "1" },
          "50%": { opacity: "0.2" },
        },
      },
      animation: {
        "message-in": "message-in 180ms ease-out both",
        cursor: "cursor 1s ease-in-out infinite",
      },
    },
  },
  plugins: [animate],
} satisfies Config
```

## Raw `apps/web/src/index.css`

```css
@tailwind base;
@tailwind components;
@tailwind utilities;

@layer base {
  :root {
    font-family: Inter, "PingFang SC", "Microsoft YaHei", system-ui, -apple-system, sans-serif;
    color: #17212b;
    background: #f4f7f9;
    font-synthesis: none;
    text-rendering: optimizeLegibility;
    -webkit-font-smoothing: antialiased;
    --background: 203 29% 97%;
    --foreground: 210 30% 13%;
    --primary: 214 83% 56%;
    --primary-foreground: 0 0% 100%;
    --muted: 204 20% 96%;
    --muted-foreground: 210 12% 45%;
    --border: 207 25% 92%;
    --input: 207 25% 92%;
    --ring: 214 83% 56%;
    --radius: 0.9rem;
  }

  * { @apply border-border; }
  html, body, #root { min-height: 100%; margin: 0; }
  body { min-width: 320px; min-height: 100dvh; overflow: hidden; }
  button, textarea { font: inherit; }
}

@layer utilities {
  .safe-top { padding-top: env(safe-area-inset-top, 0px); }
  .app-backdrop {
    background:
      radial-gradient(circle at 15% 10%, rgba(47, 128, 237, 0.08), transparent 26rem),
      radial-gradient(circle at 85% 85%, rgba(34, 168, 154, 0.07), transparent 24rem),
      #e5ebf0;
  }
  .composer-fade { background: linear-gradient(to top, #f4f7f9 68%, rgba(244, 247, 249, 0)); }
  .chat-scroll { overscroll-behavior: contain; scrollbar-width: none; }
  .chat-scroll::-webkit-scrollbar { display: none; }
}

@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    scroll-behavior: auto !important;
    animation-duration: 1ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 1ms !important;
  }
}
```
