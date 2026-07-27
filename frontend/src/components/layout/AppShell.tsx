import { Outlet } from "react-router-dom";

import { RightPanel } from "@/components/layout/RightPanel";
import { Sidebar } from "@/components/layout/Sidebar";

export function AppShell() {
  return (
    <div className="flex h-screen w-screen">
      <Sidebar />
      <main className="flex min-w-0 flex-1 flex-col bg-bg">
        <Outlet />
      </main>
      <RightPanel />
    </div>
  );
}
