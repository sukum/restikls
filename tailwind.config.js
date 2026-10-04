/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./templates/**/*.html",
  ],
  theme: {
    extend: {},
  },
  plugins: [],
  safelist: [
    "bg-red-100",
    "bg-blue-100",
    "bg-green-100",
    "bg-pink-100",
    "bg-yellow-100",
    "bg-indigo-100",
    "bg-purple-100",
    "text-red-700",
    "text-blue-700",
    "text-green-700",
    "text-pink-700",
    "text-yellow-700",
    "text-indigo-700",
    "text-purple-700",
  ],
}