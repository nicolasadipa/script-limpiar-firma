import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        // Paleta oficial ADIPA
        adipa: {
          primary: "#704EFD",        // morado principal (sitio + aula)
          cyan: "#72CAF7",
          blue: "#2CB7FF",
          bg: "#F3F4FF",             // light lavender bg
          ink: "#091E42",            // dark navy text
          "light-blue": "#CBE8FF",
          "light-purple": "#DFD5FF",
        },
      },
      fontFamily: {
        sans: ["ui-sans-serif", "system-ui", "-apple-system", "Segoe UI", "Roboto", "sans-serif"],
      },
    },
  },
  plugins: [],
};

export default config;
