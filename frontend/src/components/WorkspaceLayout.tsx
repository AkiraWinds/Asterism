"use client";

import { ReactNode } from "react";
import { Panel, Group, Separator, useDefaultLayout } from "react-resizable-panels";

interface WorkspaceLayoutProps {
  deleteError?: ReactNode;
  libraryColumn: ReactNode;
  readerPane: ReactNode;
  chatPanel: ReactNode;
}

// Guards every localStorage access so a corrupted/tampered stored value (or
// storage being unavailable, e.g. private-browsing quota errors, or absent
// entirely during SSR where `localStorage` is undefined) can never throw
// during render. getItem additionally round-trips the value through
// JSON.parse itself: the library's own defaultLayout derivation does an
// unguarded JSON.parse on whatever getItem returns, so invalid JSON has to
// be filtered out here rather than relying on the caller to catch it.
const safeStorage = {
  getItem: (key: string) => {
    try {
      const value = localStorage.getItem(key);
      JSON.parse(value ?? "null");
      return value;
    } catch {
      return null;
    }
  },
  setItem: (key: string, value: string) => {
    try {
      localStorage.setItem(key, value);
    } catch {
      // Storage full/blocked — silently skip persistence rather than crash.
    }
  },
};

export function WorkspaceLayout({
  deleteError,
  libraryColumn,
  readerPane,
  chatPanel,
}: WorkspaceLayoutProps) {
  const { defaultLayout, onLayoutChanged } = useDefaultLayout({
    id: "asterism-workspace-layout",
    storage: safeStorage,
  });

  return (
    <Group
      orientation="horizontal"
      id="asterism-workspace-layout"
      defaultLayout={defaultLayout}
      onLayoutChanged={onLayoutChanged}
      className="flex min-h-0 flex-1"
    >
      {/* minSize/defaultSize are numbers-as-pixels or strings-as-units in
          this library, never bare-number percentages — explicit "%"/"px"
          units keep these panels at their intended 25/50/25 split with
          240px/280px floors. Stable ids keep the persisted layout (see
          safeStorage above) tied to these specific panels rather than to
          tree position via React's useId(), so future markup changes don't
          silently discard a user's saved widths. */}
      <Panel defaultSize="25%" minSize="240px" id="library" className="min-w-0">
        {deleteError}
        {libraryColumn}
      </Panel>

      <Separator className="workspace-resize-handle" disableDoubleClick />

      <Panel defaultSize="50%" id="reader" className="min-w-0">
        {readerPane}
      </Panel>

      <Separator className="workspace-resize-handle" disableDoubleClick />

      <Panel defaultSize="25%" minSize="280px" id="chat" className="min-w-0">
        {chatPanel}
      </Panel>
    </Group>
  );
}
