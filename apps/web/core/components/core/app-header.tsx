/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import type { ReactNode } from "react";
import { observer } from "mobx-react";
// plane imports
import { Row } from "@plane/ui";
// components
import { cn } from "@plane/utils";
import { ExtendedAppHeader } from "@/plane-web/components/common/extended-app-header";

export interface AppHeaderProps {
  header: ReactNode;
  mobileHeader?: ReactNode;
  className?: string;
  rowClassName?: string;
}

const konnecctEmbedShell = import.meta.env.VITE_KONNECCT_EMBED_SHELL === "1";

export const AppHeader = observer(function AppHeader(props: AppHeaderProps) {
  const { header, mobileHeader, className, rowClassName } = props;

  if (konnecctEmbedShell) {
    return (
      <div className={cn("z-[18] flex min-h-0 flex-1 flex-col", className)}>
        <div className="w-full min-h-0 flex-1">{header}</div>
        {mobileHeader && mobileHeader}
      </div>
    );
  }

  return (
    <div className={cn("z-[18]", className)}>
      <Row className={cn("flex h-11 w-full items-center gap-2 border-b border-subtle bg-surface-1", rowClassName)}>
        <ExtendedAppHeader header={header} />
      </Row>
      {mobileHeader && mobileHeader}
    </div>
  );
});
