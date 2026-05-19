import { defineConfig, globalIgnores } from "eslint/config";
import nextVitals from "eslint-config-next/core-web-vitals";
import nextTs from "eslint-config-next/typescript";

const eslintConfig = defineConfig([
  ...nextVitals,
  ...nextTs,
  // Override default ignores of eslint-config-next.
  globalIgnores([
    // Default ignores of eslint-config-next:
    ".next/**",
    "out/**",
    "build/**",
    "next-env.d.ts",
  ]),
  {
    files: ["**/*.{ts,tsx,js,jsx}"],
    rules: {
      // All user confirmations/notices must use the custom ConfirmDialog
      // (see components/ui/confirm-dialog.tsx) so the UX stays consistent.
      "no-restricted-syntax": [
        "error",
        {
          selector:
            "CallExpression[callee.object.name='window'][callee.property.name=/^(confirm|alert|prompt)$/]",
          message:
            "Do not use window.confirm/alert/prompt. Use the ConfirmDialog primitive (components/ui/confirm-dialog.tsx) instead.",
        },
        {
          selector:
            "CallExpression[callee.type='Identifier'][callee.name=/^(confirm|alert|prompt)$/]",
          message:
            "Do not use global confirm/alert/prompt. Use the ConfirmDialog primitive (components/ui/confirm-dialog.tsx) instead.",
        },
      ],
    },
  },
]);

export default eslintConfig;
