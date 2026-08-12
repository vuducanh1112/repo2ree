import { Button } from "../../shared/components/Button";
import { Ic } from "../../shared/components/Icon";

export function GlassCancelButton({ onClick }: { onClick: () => void }) {
  return (
    <Button variant="danger" onClick={onClick} icon={Ic.x(14)} fullWidth>
      Cancel
    </Button>
  );
}
