import type { AuthoringStep } from "@core/app-shell/authoringDag";
import { useQuery } from "@tanstack/react-query";
import { useApiServices } from "../apiRuntime";
import { queryKeys } from "../queryKeys";

/** The authoring graph is deployment-static, so one successful fetch lasts the session. */
export function useAuthoringStepsQuery() {
  const { reeApi } = useApiServices();
  return useQuery<AuthoringStep[]>({
    queryKey: queryKeys.reeSteps(),
    queryFn: async () => {
      const catalog = await reeApi.listReeSteps();
      return [...(catalog.steps ?? [])]
        .map((step) => ({
          key: step.key,
          order: step.order,
          label: step.label,
          requires: step.requires ?? [],
          actions: step.actions ?? [],
        }))
        .sort((left, right) => left.order - right.order);
    },
    staleTime: Number.POSITIVE_INFINITY,
  });
}
