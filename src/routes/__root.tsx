import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import {
  Outlet,
  Link,
  createRootRouteWithContext,
  useRouter,
  HeadContent,
  Scripts,
} from "@tanstack/react-router";
import { Toaster } from "sonner";

import appCss from "../styles.css?url";
import { Sidebar } from "@/components/Sidebar";

function NotFoundComponent() {
  return (
    <div
      className="flex min-h-screen items-center justify-center px-4"
      style={{ background: "var(--bg-base)" }}
    >
      <div className="max-w-md text-center">
        <h1 className="font-display italic text-[120px] leading-none" style={{ color: "var(--text-muted)" }}>
          404
        </h1>
        <p
          className="mt-4 font-ui uppercase text-[12px] tracking-widest-2"
          style={{ color: "var(--text-secondary)" }}
        >
          Page not found
        </p>
        <Link
          to="/"
          className="mt-6 inline-block font-ui uppercase text-[11px] tracking-widest-2 px-5 py-3 rounded-md"
          style={{ background: "var(--accent)", color: "#0A0A0F" }}
        >
          Back to Scrape
        </Link>
      </div>
    </div>
  );
}

function ErrorComponent({ error, reset }: { error: Error; reset: () => void }) {
  console.error(error);
  const router = useRouter();
  return (
    <div
      className="flex min-h-screen items-center justify-center px-4"
      style={{ background: "var(--bg-base)" }}
    >
      <div className="max-w-md text-center">
        <h1 className="font-display italic text-[28px]" style={{ color: "var(--text-primary)" }}>
          Something broke
        </h1>
        <p
          className="mt-3 font-ui uppercase text-[11px] tracking-widest-2"
          style={{ color: "var(--text-secondary)" }}
        >
          {error.message}
        </p>
        <button
          onClick={() => {
            router.invalidate();
            reset();
          }}
          className="mt-6 font-ui uppercase text-[11px] tracking-widest-2 px-5 py-3 rounded-md"
          style={{ background: "var(--accent)", color: "#0A0A0F" }}
        >
          Try Again
        </button>
      </div>
    </div>
  );
}

export const Route = createRootRouteWithContext<{ queryClient: QueryClient }>()({
  head: () => ({
    meta: [
      { charSet: "utf-8" },
      { name: "viewport", content: "width=device-width, initial-scale=1" },
      { title: "UniScraper — Admission Intelligence" },
      {
        name: "description",
        content:
          "Dark-mode intelligence dashboard for scraping and extracting university admission data with AI.",
      },
      { property: "og:title", content: "UniScraper — Admission Intelligence" },
      {
        property: "og:description",
        content: "Scrape university program pages, extract admission data with AI.",
      },
      { property: "og:type", content: "website" },
    ],
    links: [{ rel: "stylesheet", href: appCss }],
  }),
  shellComponent: RootShell,
  component: RootComponent,
  notFoundComponent: NotFoundComponent,
  errorComponent: ErrorComponent,
});

function RootShell({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <head>
        <HeadContent />
      </head>
      <body>
        {children}
        <Scripts />
      </body>
    </html>
  );
}

function RootComponent() {
  const { queryClient } = Route.useRouteContext();
  return (
    <QueryClientProvider client={queryClient}>
      <div className="min-h-screen w-full" style={{ background: "var(--bg-base)" }}>
        <Sidebar />
        <main className="md:ml-[220px] min-h-screen page-in" key={typeof window !== "undefined" ? window.location.pathname : "ssr"}>
          <Outlet />
        </main>
        <Toaster
          theme="dark"
          position="top-right"
          toastOptions={{
            style: {
              background: "rgba(26,26,36,0.85)",
              backdropFilter: "blur(12px)",
              border: "1px solid var(--border)",
              color: "var(--text-primary)",
              fontFamily: "var(--font-ui)",
              fontSize: "13px",
            },
          }}
        />
      </div>
    </QueryClientProvider>
  );
}
