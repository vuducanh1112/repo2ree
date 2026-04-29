import { useMemo } from "react";
import { AppBootstrap } from "./app/AppBootstrap";
import { createBrowserRuntimePorts } from "./app/browserRuntimePorts";
import { DEMO_REE } from "./app/demoRee";
import { createMockWorkspaceGateway } from "./app/mockWorkspaceGateway";
import { WorkspaceRuntimeProvider, type WorkspaceRuntimeValue } from "./app/WorkspaceRuntime";
import { WORKSPACE_ID } from "./app/workspaceConstants";
import { WorkspaceEditorProvider } from "./context";
import { createHttpWorkspaceGateway } from "./workspace/HttpWorkspaceGateway";

export default function App() {
  const runtime = useMemo<WorkspaceRuntimeValue>(() => {
    const env =
      (import.meta as ImportMeta & { env?: Record<string, string | undefined> }).env || {};
    const explicitMode = String(env.VITE_WORKSPACE_SERVICE_MODE || "").toLowerCase();
    const workspaceServiceMode: "remote" | "mock" =
      explicitMode === "remote" || (!explicitMode && env.VITE_API_BASE_URL) ? "remote" : "mock";
    const reeIdFromQuery =
      typeof window !== "undefined"
        ? new URLSearchParams(window.location.search).get("reeId") || undefined
        : undefined;
    const remoteWorkspaceService =
      workspaceServiceMode === "remote"
        ? createHttpWorkspaceGateway({
            baseUrl: env.VITE_API_BASE_URL || "",
            initialWorkspaceId: reeIdFromQuery,
          })
        : null;
    const ports = createBrowserRuntimePorts();

    return {
      workspaceId: WORKSPACE_ID,
      workspaceServiceMode,
      ports,
      createWorkspaceService: (args) =>
        remoteWorkspaceService || createMockWorkspaceGateway({ ...args, ports }),
    };
  }, []);

  return (
    <WorkspaceRuntimeProvider value={runtime}>
      <WorkspaceEditorProvider initialExplorerRee={DEMO_REE}>
        <AppBootstrap />
      </WorkspaceEditorProvider>
    </WorkspaceRuntimeProvider>
  );
}
