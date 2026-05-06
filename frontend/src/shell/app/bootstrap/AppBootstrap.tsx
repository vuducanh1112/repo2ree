import { AppRoutes } from "../../../ui/routes";
import { GLOBAL_CSS } from "../../../ui/theme/globalCss";

export function AppBootstrap() {
  return (
    <>
      <style>{GLOBAL_CSS}</style>
      <AppRoutes />
    </>
  );
}
