"use client";

/**
 * Last-resort boundary. Catches errors thrown by the *root layout* itself —
 * at that point `app/layout.tsx` has failed, so this component must supply its
 * own <html> and <body>.
 *
 * Intentionally written with inline styles and no imports: if the root layout
 * blew up, the font loader, the QueryProvider, or the stylesheet itself are all
 * suspects, so this page must render correctly with zero app CSS and zero app
 * components. Every other boundary (app/error.tsx, the dashboard one) is the
 * nicely-styled path; this one only has to work.
 */
export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <html lang="en">
      <body
        style={{
          margin: 0,
          minHeight: "100vh",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          padding: "2rem",
          fontFamily:
            "ui-sans-serif, system-ui, -apple-system, 'Segoe UI', sans-serif",
          background: "#fff",
          color: "#0a0a0a",
        }}
      >
        <div style={{ maxWidth: "28rem", textAlign: "center" }}>
          <h1 style={{ fontSize: "1.125rem", fontWeight: 600, margin: 0 }}>
            Matrix Science Academy
          </h1>
          <p style={{ margin: "0.75rem 0 0", fontSize: "0.875rem" }}>
            The application failed to start. This is not something you did —
            reloading usually clears it.
          </p>
          <button
            onClick={() => reset()}
            style={{
              marginTop: "1.25rem",
              padding: "0.5rem 1rem",
              fontSize: "0.875rem",
              fontWeight: 500,
              color: "#fff",
              background: "#0a0a0a",
              border: "none",
              borderRadius: "0.5rem",
              cursor: "pointer",
            }}
          >
            Reload
          </button>
          {error.digest && (
            <p
              style={{
                marginTop: "1.25rem",
                fontSize: "0.75rem",
                fontFamily: "ui-monospace, monospace",
                color: "#737373",
              }}
            >
              Reference: {error.digest}
            </p>
          )}
        </div>
      </body>
    </html>
  );
}
