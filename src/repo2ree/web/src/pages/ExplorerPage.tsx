interface ExplorerPageProps {
  ExplorerView: React.ComponentType<{ onBack: () => void }>;
  onBack: () => void;
}

export function ExplorerPage({ ExplorerView, onBack }: ExplorerPageProps) {
  return <ExplorerView onBack={onBack} />;
}
