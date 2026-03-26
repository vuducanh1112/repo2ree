interface ReviewerPageProps {
  ReviewerView: React.ComponentType<{ onBack: () => void }>;
  onBack: () => void;
}

export function ReviewerPage({ ReviewerView, onBack }: ReviewerPageProps) {
  return <ReviewerView onBack={onBack} />;
}
