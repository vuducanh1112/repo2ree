import { QueryClientProvider } from "@tanstack/react-query";
import { useMemo } from "react";
import { createHttpArtifactRepository } from "./infra/repositories/HttpArtifactRepository";
import { createHttpRepositoryClient } from "./infra/repositories/HttpRepositoryClient";
import { createHttpReviewRepository } from "./infra/repositories/HttpReviewRepository";
import { createHttpWorkflowRunRepository } from "./infra/repositories/HttpWorkflowRunRepository";
import { createHttpWorkspaceRepository } from "./infra/repositories/HttpWorkspaceRepository";
import { AppBootstrap } from "./runtime/bootstrap/AppBootstrap";
import {
  WorkspaceRuntimeProvider,
  type WorkspaceRuntimeValue,
} from "./runtime/browser/BrowserRuntime";
import { createBrowserRuntimePorts } from "./runtime/browser/BrowserRuntimePorts";
import { WORKSPACE_ID } from "./runtime/config/WorkspaceConstants";
import { createAppQueryClient } from "./runtime/query/queryClient";
import { AppShellProvider } from "./ui/app-shell/providers/AppShellProvider";

export default function App() {
  const queryClient = useMemo(() => createAppQueryClient(), []);
  const runtime = useMemo<WorkspaceRuntimeValue>(() => {
    const env =
      (import.meta as ImportMeta & { env?: Record<string, string | undefined> }).env || {};
    const reeIdFromQuery =
      typeof window !== "undefined"
        ? new URLSearchParams(window.location.search).get("reeId") || undefined
        : undefined;
    const repositoryClient = createHttpRepositoryClient({
      baseUrl: env.VITE_API_BASE_URL || "",
      initialWorkspaceId: reeIdFromQuery,
    });
    const ports = createBrowserRuntimePorts();

    return {
      workspaceId: WORKSPACE_ID,
      ports,
      workspaceRepository: createHttpWorkspaceRepository(repositoryClient),
      workflowRunRepository: createHttpWorkflowRunRepository(repositoryClient),
      artifactRepository: createHttpArtifactRepository(repositoryClient),
      reviewRepository: createHttpReviewRepository({
        baseUrl: env.VITE_API_BASE_URL || "",
      }),
    };
  }, []);

  return (
    <QueryClientProvider client={queryClient}>
      <WorkspaceRuntimeProvider value={runtime}>
        <AppShellProvider>
          <AppBootstrap />
        </AppShellProvider>
      </WorkspaceRuntimeProvider>
    </QueryClientProvider>
  );
}
