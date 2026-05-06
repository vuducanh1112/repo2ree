import { Ic } from "../../../../shared/components/Icon";
import { F } from "../../../../theme/theme";
import { AssemblyPageHeader } from "../../../components/pageChrome";
import { assemblyToneSurfaceStyle } from "../../../components/statusUiStyles";

interface HardwareBomHeaderSectionProps {
  locked: boolean;
  onUnlock: () => void;
}

export function HardwareBomHeaderSection({ locked, onUnlock }: HardwareBomHeaderSectionProps) {
  return (
    <AssemblyPageHeader
      color="#0f766e"
      icon={Ic.chip(18)}
      title="Create Hardware BOM"
      subtitle="Document the machine assumptions that matter today and can later expand to remote targets"
      tips={[
        "Each category is keyed by device model, matching the structured HBOM format stored in the REE draft.",
        "Only the device model is required. Other fields can stay at their defaults and will persist immediately.",
        "Use Profile This Machine to prefill the table, then adjust any rows manually before moving on.",
      ]}
      rightAction={
        locked ? (
          <button
            type="button"
            onClick={onUnlock}
            style={{
              display: "flex",
              alignItems: "center",
              gap: 6,
              padding: "6px 12px",
              ...assemblyToneSurfaceStyle("warn"),
              borderRadius: 6,
              cursor: "pointer",
              fontSize: 13,
              fontFamily: F.sans,
              fontWeight: 600,
              flexShrink: 0,
            }}
          >
            {Ic.unlock(13)} Unlock fields
          </button>
        ) : null
      }
    />
  );
}
