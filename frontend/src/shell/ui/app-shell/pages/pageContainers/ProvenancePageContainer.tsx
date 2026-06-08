import { useApiRuntime } from "../../../../data/apiRuntime";
import { useReceiptsQuery } from "../../../../data/receipts/queries";
import { PAGE } from "../../state/pages";
import { ProvenancePage } from "../provenance/ProvenancePage";
import { type AppShellPageContainerProps, ContentSection } from "./shared";

export function ProvenancePageContainer({ uiChrome }: AppShellPageContainerProps) {
  const { reeId } = useApiRuntime();
  const { page } = uiChrome;
  const { data: receipts, isLoading } = useReceiptsQuery(reeId);

  if (page !== PAGE.PROVENANCE) {
    return null;
  }

  return (
    <ContentSection>
      <ProvenancePage receipts={receipts ?? []} loading={isLoading} />
    </ContentSection>
  );
}
