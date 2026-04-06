/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { startTransition, StrictMode } from "react";
import { createRoot, hydrateRoot } from "react-dom/client";
import { HydratedRouter } from "react-router/dom";

const MF_ROOT_ID = "konnecct-plane-mf-root";

startTransition(() => {
  const useMfHost = typeof window !== "undefined" && window.__KONNECCT_PLANE_MF_HOST__ === true;
  const mfEl = typeof document !== "undefined" ? document.getElementById(MF_ROOT_ID) : null;
  const app = (
    <StrictMode>
      <HydratedRouter />
    </StrictMode>
  );

  if (useMfHost) {
    if (!mfEl) {
      return;
    }
    createRoot(mfEl).render(app);
    return;
  }
  hydrateRoot(document, app);
});
