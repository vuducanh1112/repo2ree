import { AppBootstrap } from "./app/AppBootstrap";
import { DEMO_REE } from "./app/demoRee";
import { AppProvider } from "./context";

export default function App() {
  return (
    <AppProvider initialExplorerRee={DEMO_REE}>
      <AppBootstrap />
    </AppProvider>
  );
}
