import { Route, Routes } from "react-router-dom";

import { AppShell } from "@/components/layout/AppShell";
import { ChatRoute } from "@/routes/ChatRoute";
import { ProjectRoute } from "@/routes/ProjectRoute";
import { ToolsCatalogRoute } from "@/routes/ToolsCatalogRoute";

export function App() {
  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route index element={<ChatRoute />} />
        <Route path="chats/:chatId" element={<ChatRoute />} />
        <Route path="projects/:projectId" element={<ProjectRoute />} />
        <Route path="projects/:projectId/chats/:chatId" element={<ChatRoute />} />
        <Route path="tools" element={<ToolsCatalogRoute />} />
      </Route>
    </Routes>
  );
}
