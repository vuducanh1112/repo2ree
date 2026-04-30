import { QueryClientProvider } from "@tanstack/react-query";
import { useMemo } from "react";
import { createHttpWorkspaceBackendGateway } from "./infra/workspace/HttpWorkspaceBackendGateway";
import { AppBootstrap } from "./runtime/bootstrap/AppBootstrap";
import {
  WorkspaceRuntimeProvider,
  type WorkspaceRuntimeValue,
} from "./runtime/browser/BrowserRuntime";
import { createBrowserRuntimePorts } from "./runtime/browser/BrowserRuntimePorts";
import { WORKSPACE_ID } from "./runtime/config/WorkspaceConstants";
import { DEMO_REE } from "./runtime/demo/DemoRee";
import { createAppQueryClient } from "./runtime/query/queryClient";
import { WorkspaceEditorProvider } from "./ui/workspace-editor/providers/WorkspaceEditorProvider";

export default function App() {
  const queryClient = useMemo(() => createAppQueryClient(), []);
  const runtime = useMemo<WorkspaceRuntimeValue>(() => {
    const env =
      (import.meta as ImportMeta & { env?: Record<string, string | undefined> }).env || {};
    const reeIdFromQuery =
      typeof window !== "undefined"
        ? new URLSearchParams(window.location.search).get("reeId") || undefined
        : undefined;
    const workspaceBackend = createHttpWorkspaceBackendGateway({
      baseUrl: env.VITE_API_BASE_URL || "",
      initialWorkspaceId: reeIdFromQuery,
    });
    const ports = createBrowserRuntimePorts();

    return {
      workspaceId: WORKSPACE_ID,
      ports,
      workspaceBackend,
    };
  }, []);

  return (
    <QueryClientProvider client={queryClient}>
      <WorkspaceRuntimeProvider value={runtime}>
        <WorkspaceEditorProvider initialWorkspaceEditorRee={DEMO_REE}>
          <AppBootstrap />
        </WorkspaceEditorProvider>
      </WorkspaceRuntimeProvider>
    </QueryClientProvider>
  );
}
