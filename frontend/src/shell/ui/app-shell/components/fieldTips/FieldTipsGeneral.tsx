import { Ic } from "../../../shared/components/Icon";
import { C, S_SECTION_LABEL } from "../../../theme/theme";

interface FieldTipsGeneralProps {
  generalTips: string[];
  generalTitle: string;
}

export function FieldTipsGeneral({ generalTips, generalTitle }: FieldTipsGeneralProps) {
  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        gap: 6,
      }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 7,
        }}
      >
        <span
          style={{
            color: C.textMid,
            display: "flex",
          }}
        >
          {Ic.info(13)}
        </span>
        <span
          style={{
            ...S_SECTION_LABEL,
            letterSpacing: 0.8,
            color: C.textMid,
          }}
        >
          {generalTitle}
        </span>
      </div>
      <div
        style={{
          display: "flex",
          flexDirection: "column",
          gap: 6,
        }}
      >
        {generalTips.map((tip) => (
          <p
            key={tip}
            style={{
              margin: 0,
              fontSize: 12,
              color: C.textMid,
              lineHeight: 1.55,
            }}
          >
            {tip}
          </p>
        ))}
      </div>
    </div>
  );
}
