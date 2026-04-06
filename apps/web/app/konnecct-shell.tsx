/**
 * Module Federation remote shell for Twenty (Konnecct host). Reuses the same
 * bootstrap module Graph as index.html, then mounts via entry.client
 * (createRoot on #konnecct-plane-mf-root).
 */
import { startTransition, StrictMode, useEffect, useLayoutEffect, useRef, useState } from "react";
import { LogoSpinner } from "@/components/common/logo-spinner";

const MF_ROOT_ID = "konnecct-plane-mf-root";

export type KonnecctShellProps = {
  konnecctPathSuffix?: string;
  konnecctPlaneBasename?: string;
};

const normalizeBasename = (b: string) => b.replace(/\/$/, "") || "";

const normalizeSuffix = (s: string) => {
  if (!s || s === "") return "/";
  return s.startsWith("/") ? s : `/${s}`;
};

const extractRouterModuleScript = (html: string): string | null => {
  const doc = new DOMParser().parseFromString(html, "text/html");
  const modules = Array.from(doc.querySelectorAll("script[type='module']"));
  for (const el of modules) {
    const t = el.textContent ?? "";
    if (t.includes("__reactRouterRouteModules")) {
      return t;
    }
  }
  for (const el of modules) {
    const t = el.textContent ?? "";
    if (t.includes("__reactRouter")) {
      return t;
    }
  }
  return null;
};

const ensureBootstrap = (indexUrl: string): Promise<void> => {
  return (window.__konnecctPlaneBootstrapPromise ??= (async () => {
    const res = await fetch(indexUrl, { credentials: "include" });
    const html = await res.text();
    const moduleSrc = extractRouterModuleScript(html);
    if (!moduleSrc) {
      throw new Error("KonnecctShell: no React Router bootstrap script in Plane index.html");
    }

    const mountHost = document.getElementById(MF_ROOT_ID);
    if (!mountHost) {
      throw new Error("KonnecctShell: mount node #" + MF_ROOT_ID + " missing");
    }

    await new Promise<void>((resolve, reject) => {
      const url = URL.createObjectURL(new Blob([moduleSrc], { type: "text/javascript" }));
      const tag = document.createElement("script");
      tag.type = "module";
      tag.src = url;
      tag.onload = () => {
        URL.revokeObjectURL(url);
        resolve();
      };
      tag.onerror = () => {
        URL.revokeObjectURL(url);
        reject(new Error("KonnecctShell: failed to execute Plane bootstrap"));
      };
      document.head.appendChild(tag);
    });
  })());
};

export default function KonnecctShell({
  konnecctPathSuffix = "/",
  konnecctPlaneBasename = "/_konnecct/plane",
}: KonnecctShellProps) {
  const shellRef = useRef<HTMLDivElement>(null);
  const [bootError, setBootError] = useState<string | null>(null);
  const [showSpinner, setShowSpinner] = useState(true);

  useLayoutEffect(() => {
    const shell = shellRef.current;
    if (!shell) {
      return;
    }

    const basename = normalizeBasename(konnecctPlaneBasename);
    const suffix = normalizeSuffix(konnecctPathSuffix);
    const pathAfterBasename = suffix === "/" ? "" : suffix;
    const targetPath = `${basename}${pathAfterBasename}`;

    window.history.replaceState(window.history.state, "", targetPath);
    window.__KONNECCT_PLANE_MF_HOST__ = true;

    const indexUrl = new URL(`${basename}/`, window.location.origin).toString();
    if (new URL(indexUrl).origin !== window.location.origin) {
      setBootError("KonnecctShell: Plane index must be same-origin.");
      setShowSpinner(false);
      return;
    }

    let cancelled = false;
    setBootError(null);
    setShowSpinner(true);

    void (async () => {
      try {
        await ensureBootstrap(indexUrl);
        if (cancelled) {
          return;
        }
        const router = window.__reactRouterDataRouter;
        if (router) {
          startTransition(() => {
            router.navigate(pathAfterBasename === "" ? "/" : pathAfterBasename);
          });
        }
        setShowSpinner(false);
      } catch (e) {
        if (!cancelled) {
          setBootError(e instanceof Error ? e.message : String(e));
          setShowSpinner(false);
        }
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [konnecctPlaneBasename, konnecctPathSuffix]);

  useEffect(() => {
    return () => {
      window.__KONNECCT_PLANE_MF_HOST__ = false;
    };
  }, []);

  if (bootError) {
    return (
      <div className="flex h-full w-full items-center justify-center bg-canvas p-6 text-center text-14 text-primary">
        {bootError}
      </div>
    );
  }

  return (
    <div ref={shellRef} className="relative h-full w-full min-h-0 overflow-hidden bg-canvas">
      <div id={MF_ROOT_ID} className="relative h-full w-full min-h-0" />
      {showSpinner ? (
        <div className="absolute inset-0 z-10 flex items-center justify-center bg-canvas">
          <StrictMode>
            <LogoSpinner />
          </StrictMode>
        </div>
      ) : null}
    </div>
  );
}
