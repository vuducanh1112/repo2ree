import { lgColors, lgStyles } from "../../../theme/lightGlassTheme";
import { F } from "../../../theme/theme";

interface Step3Props {
  step3Ready: boolean;
  acquisitionNarrative: string;
}

export function SourceStep3Section(props: Step3Props) {
  return (
    <div style={{ borderTop: "1px solid rgba(125, 211, 252, 0.28)", paddingTop: 20 }}>
      <div style={{ ...lgStyles.label, marginBottom: 10 }}>Workspace Snapshot</div>

      {props.step3Ready ? (
        <div style={{ fontSize: 13, color: lgColors.textMid, fontFamily: F.sans }}>
          {props.acquisitionNarrative}
        </div>
      ) : (
        <div style={lgStyles.helper}>
          Complete the Source Snapshot step above to configure snapshot behavior.
        </div>
      )}
    </div>
  );
}
