import coreWebVitals from "eslint-config-next/core-web-vitals";
import typescript from "eslint-config-next/typescript";

const config = [
  ...coreWebVitals,
  ...typescript,
  { ignores: ["coverage/**", ".next/**", "node_modules/**", "src/data/**"] },
];

export default config;
