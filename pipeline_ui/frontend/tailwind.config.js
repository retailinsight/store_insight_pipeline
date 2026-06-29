/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink:    "#0b1026",
        muted:  "#64748b",
        accent: "#6d28d9", // deep violet
      },
      backgroundImage: {
        "app-gradient":    "linear-gradient(135deg, #eef2ff 0%, #fef6ff 40%, #fff1f5 100%)",
        "header-gradient": "linear-gradient(90deg, #6d28d9 0%, #db2777 100%)",
      },
      boxShadow: {
        soft: "0 1px 3px rgba(15,23,42,0.04), 0 4px 18px -6px rgba(109,40,217,0.12)",
      },
    },
  },
  plugins: [],
};
