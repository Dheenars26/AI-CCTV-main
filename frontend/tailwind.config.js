/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        soc: {
          bg: "#F8FAFC",
          card: "#FFFFFF",
          border: "#E2E8F0",
          hover: "#F1F5F9",
          text: "#0F172A",
          muted: "#64748B",
          primary: "#2563EB",
          accent: "#3B82F6",
          fire: "#E11D48",
          smoke: "#D97706",
          online: "#10B981",
          offline: "#94A3B8",
          // Retain legacy keys mapped to light-friendly tones
          darkbg: "#080B11",
          darkcard: "#0F1623",
        }
      },
      boxShadow: {
        'card': '0 1px 3px 0 rgba(0, 0, 0, 0.05), 0 1px 2px -1px rgba(0, 0, 0, 0.05)',
        'card-hover': '0 4px 6px -1px rgba(0, 0, 0, 0.07), 0 2px 4px -2px rgba(0, 0, 0, 0.05)',
        'modal': '0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 8px 10px -6px rgba(0, 0, 0, 0.06)',
        'primary-glow': '0 4px 14px 0 rgba(37, 99, 235, 0.25)',
      },
      animation: {
        'pulse-fast': 'pulse 1s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'glow-fire': 'glowFire 1.5s ease-in-out infinite alternate',
      },
      keyframes: {
        glowFire: {
          '0%': { boxShadow: '0 0 8px rgba(225, 29, 72, 0.3)' },
          '100%': { boxShadow: '0 0 20px rgba(225, 29, 72, 0.6)' },
        }
      }
    },
  },
  plugins: [],
}
