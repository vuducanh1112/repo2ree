export const ACTION_TYPES = {
  app: {
    setPage: "app/setPage",
  },
  explorer: {
    setRee: "explorer/setRee",
    setLocked: "explorer/setLocked",
    setRepoMode: "explorer/setRepoMode",
    setActionStates: "explorer/setActionStates",
    setBadges: "explorer/setBadges",
    setTimestamps: "explorer/setTimestamps",
    setServiceLogs: "explorer/setServiceLogs",
    setServiceParams: "explorer/setServiceParams",
    setToast: "explorer/setToast",
    setPage: "explorer/setPage",
    setFocusedField: "explorer/setFocusedField",
    setNavCollapsed: "explorer/setNavCollapsed",
    setVirtualFiles: "explorer/setVirtualFiles",
    setImmutableSourceSnapshotFiles: "explorer/setImmutableSourceSnapshotFiles",
    setImmutableSourceSnapshotArchiveName: "explorer/setImmutableSourceSnapshotArchiveName",
    setShowReviewerPreview: "explorer/setShowReviewerPreview",
    resetWorkflowOnSourceChange: "explorer/resetWorkflowOnSourceChange",
  },
} as const;
