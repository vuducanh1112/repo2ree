import type { ApiServicesValue } from "@shell/data/apiRuntime";
import { ApiServicesProvider, ReeScopeProvider } from "@shell/data/apiRuntime";
import { QueryClientProvider } from "@tanstack/react-query";
import { type RenderOptions, type RenderResult, render } from "@testing-library/react";
import type { ReactElement, ReactNode } from "react";
import { MemoryRouter } from "react-router";
import { fakeApiServices } from "./fakeApiServices";
import { createTestQueryClient } from "./testQueryClient";

interface ShellProviderOptions {
  route?: string;
  reeId?: string;
  services?: ApiServicesValue;
}

interface ShellRenderOptions extends Omit<RenderOptions, "wrapper">, ShellProviderOptions {}

export function createShellWrapper({
  route = "/",
  reeId,
  services = fakeApiServices(),
}: ShellProviderOptions = {}) {
  const queryClient = createTestQueryClient();

  function Wrapper({ children }: { children: ReactNode }) {
    const content = reeId ? (
      <ReeScopeProvider reeId={reeId}>{children}</ReeScopeProvider>
    ) : (
      children
    );
    return (
      <QueryClientProvider client={queryClient}>
        <ApiServicesProvider services={services}>
          <MemoryRouter initialEntries={[route]}>{content}</MemoryRouter>
        </ApiServicesProvider>
      </QueryClientProvider>
    );
  }

  return { Wrapper, queryClient };
}

export function renderWithShell(
  ui: ReactElement,
  { route = "/", reeId, services = fakeApiServices(), ...options }: ShellRenderOptions = {},
): RenderResult & { queryClient: ReturnType<typeof createTestQueryClient> } {
  const { Wrapper, queryClient } = createShellWrapper({ route, reeId, services });

  return { ...render(ui, { wrapper: Wrapper, ...options }), queryClient };
}
