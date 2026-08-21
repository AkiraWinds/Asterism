"use client";

import { ReactNode } from "react";
import { Panel, Group, Separator, useDefaultLayout } from "react-resizable-panels";

interface WorkspaceLayoutProps {
  deleteError?: ReactNode;
  libraryColumn: ReactNode;
  readerPane: ReactNode;
  chatPanel: ReactNode;
}

export function WorkspaceLayout({
  deleteError,
  libraryColumn,
  readerPane,
  chatPanel,
}: WorkspaceLayoutProps) {
  const { defaultLayout, onLayoutChanged } = useDefaultLayout({
    id: "asterism-workspace-layout",
  });

  return (
    <Group
      orientation="horizontal"
      id="asterism-workspace-layout"
      defaultLayout={defaultLayout}
      onLayoutChanged={onLayoutChanged}
      className="flex min-h-0 flex-1"
    >
      <Panel defaultSize={25} minSize={18} className="min-w-0">
        {deleteError}
        {libraryColumn}
      </Panel>

      <Separator className="workspace-resize-handle" />

      <Panel defaultSize={50} className="min-w-0">
        {readerPane}
      </Panel>

      <Separator className="workspace-resize-handle" />

      <Panel defaultSize={25} minSize={20} className="min-w-0">
        {chatPanel}
      </Panel>
    </Group>
  );
}
