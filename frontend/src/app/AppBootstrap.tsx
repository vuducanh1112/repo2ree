import { AppRoutes } from "../pages";
import { GLOBAL_CSS } from "../styles/globalCss";

export function AppBootstrap() {
  return (
    <>
      <style>{GLOBAL_CSS}</style>
      <AppRoutes />
    </>
  );
}
