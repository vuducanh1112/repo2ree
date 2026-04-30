import { useMemo } from "react";
import { createHttpWorkspaceGateway } from "./infra/workspace/HttpWorkspaceGateway";
import { AppBootstrap } from "./runtime/bootstrap/AppBootstrap";
import {
  WorkspaceRuntimeProvider,
  type WorkspaceRuntimeValue,
} from "./runtime/browser/BrowserRuntime";
import { createBrowserRuntimePorts } from "./runtime/browser/BrowserRuntimePorts";
import { WORKSPACE_ID } from "./runtime/config/WorkspaceConstants";
import { DEMO_REE } from "./runtime/demo/DemoRee";
import { createMockWorkspaceGateway } from "./runtime/demo/MockWorkspaceGatewayFactory";
import { WorkspaceEditorProvider } from "./ui/workspace-editor/providers/WorkspaceEditorProvider";

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
      <WorkspaceEditorProvider initialWorkspaceEditorRee={DEMO_REE}>
        <AppBootstrap />
      </WorkspaceEditorProvider>
    </WorkspaceRuntimeProvider>
  );
}
