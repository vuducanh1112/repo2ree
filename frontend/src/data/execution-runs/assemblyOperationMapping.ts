import type { ReeAssemblyOperation } from "../../domain/execution/ReeAssemblyOperation";
import type { WorkflowOperationDto } from "../../infra/api/apiTypes";

export function toBackendWorkflowOperation(operation: ReeAssemblyOperation): WorkflowOperationDto {
  switch (operation) {
    case "generateHbom":
      return "hbom";
    case "buildRuntime":
      return "build";
    case "generateSbom":
      return "sbom";
    case "testActivation":
      return "activation";
  }
}

export function fromBackendWorkflowOperation(
  operation: WorkflowOperationDto,
): ReeAssemblyOperation | null {
  switch (operation) {
    case "hbom":
      return "generateHbom";
    case "build":
      return "buildRuntime";
    case "sbom":
      return "generateSbom";
    case "activation":
      return "testActivation";
    default:
      return null;
  }
}
