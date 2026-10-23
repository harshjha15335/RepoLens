import { defineConfig, globalIgnores } from "eslint/config";
import nextVitals from "eslint-config-next/core-web-vitals";
import nextTs from "eslint-config-next/typescript";

const eslintConfig = defineConfig([
  ...nextVitals,
  ...nextTs,
  globalIgnores([
    ".next/**",
    ".next-audit/**",
    ".next-deploy-check/**",
    "out/**",
    "build/**",
    "next-env.d.ts",
    "sample-repos/**",
    "tests/**",
  ]),
  {
    rules: {
      "@typescript-eslint/no-empty-object-type": "off",
      "@typescript-eslint/ban-ts-comment": "off",
      "@typescript-eslint/no-unused-vars": "warn",
      "@typescript-eslint/no-explicit-any": "off",
      "react-hooks/set-state-in-effect": "off",
      "react-hooks/exhaustive-deps": "warn",
      "@next/next/no-html-link-for-pages": "off",
    },
  },
]);

export default eslintConfig;
