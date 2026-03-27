import type { ReactNode } from "react";
import { createContext, useCallback, useContext, useMemo, useState } from "react";
import { APP_PAGE, PAGE } from "../constants/pages";
import { initialServiceParams } from "../constants/services";
import { normalizeExplorerPage } from "../features/explorer/utils/navigation";
import type {
  ActionStates,
  AppPage,
  Badges,
  ExplorerPage,
  FileTreeNode,
  Ree,
  ServiceLogs,
  ServiceParams,
  Timestamps,
  ToastState,
} from "../types";
import type { AppContextState } from "./types";

interface AppContextValue {
  state: AppContextState;
  setAppPage: React.Dispatch<React.SetStateAction<AppPage>>;
  setRee: React.Dispatch<React.SetStateAction<Ree>>;
  setLocked: React.Dispatch<React.SetStateAction<boolean>>;
  setRepoMode: React.Dispatch<React.SetStateAction<"url" | "upload">>;
  setActionStates: React.Dispatch<React.SetStateAction<ActionStates>>;
  setBadges: React.Dispatch<React.SetStateAction<Badges>>;
  setTimestamps: React.Dispatch<React.SetStateAction<Timestamps>>;
  setServiceLogs: React.Dispatch<React.SetStateAction<ServiceLogs>>;
  setServiceParams: React.Dispatch<React.SetStateAction<ServiceParams>>;
  setToast: React.Dispatch<React.SetStateAction<ToastState | null>>;
  setExplorerPage: React.Dispatch<React.SetStateAction<ExplorerPage>>;
  setFocusedField: React.Dispatch<React.SetStateAction<string | null>>;
  setNavCollapsed: React.Dispatch<React.SetStateAction<boolean>>;
  setVirtualFiles: React.Dispatch<React.SetStateAction<FileTreeNode[]>>;
  setImmutableSourceSnapshotFiles: React.Dispatch<React.SetStateAction<FileTreeNode[]>>;
  setImmutableSourceSnapshotArchiveName: React.Dispatch<React.SetStateAction<string>>;
  setShowReviewerPreview: React.Dispatch<React.SetStateAction<boolean>>;
}

const AppContext = createContext<AppContextValue | null>(null);

interface AppProviderProps {
  children: ReactNode;
  initialExplorerRee: Ree;
}

export function AppProvider({ children, initialExplorerRee }: AppProviderProps) {
  const [appPage, setAppPage] = useState<AppPage>(APP_PAGE.LANDING);
  const [ree, setRee] = useState<Ree>(initialExplorerRee);
  const [locked, setLocked] = useState(false);
  const [repoMode, setRepoMode] = useState<"url" | "upload">("url");
  const [actionStates, setActionStates] = useState<ActionStates>({});
  const [badges, setBadges] = useState<Badges>({});
  const [timestamps, setTimestamps] = useState<Timestamps>({});
  const [serviceLogs, setServiceLogs] = useState<ServiceLogs>({});
  const [serviceParams, setServiceParams] = useState<ServiceParams>(() => initialServiceParams());
  const [toast, setToast] = useState<ToastState | null>(null);
  const [explorerPage, setExplorerPageState] = useState<ExplorerPage>(PAGE.SOURCE);
  const [focusedField, setFocusedField] = useState<string | null>(null);
  const [navCollapsed, setNavCollapsed] = useState(false);
  const [virtualFiles, setVirtualFiles] = useState<FileTreeNode[]>([]);
  const [immutableSourceSnapshotFiles, setImmutableSourceSnapshotFiles] = useState<FileTreeNode[]>(
    [],
  );
  const [immutableSourceSnapshotArchiveName, setImmutableSourceSnapshotArchiveName] = useState("");
  const [showReviewerPreview, setShowReviewerPreview] = useState(false);

  const setExplorerPage = useCallback<React.Dispatch<React.SetStateAction<ExplorerPage>>>(
    (nextPage) => {
      setExplorerPageState((previousPage) => {
        const resolvedPage =
          typeof nextPage === "function" ? nextPage(previousPage) : normalizeExplorerPage(nextPage);
        return normalizeExplorerPage(resolvedPage, previousPage);
      });
    },
    [],
  );

  const state = useMemo<AppContextState>(
    () => ({
      appPage,
      explorer: {
        ree,
        locked,
        repoMode,
        actionStates,
        badges,
        timestamps,
        serviceLogs,
        serviceParams,
        toast,
        page: explorerPage,
        focusedField,
        navCollapsed,
        virtualFiles,
        immutableSourceSnapshotFiles,
        immutableSourceSnapshotArchiveName,
        showReviewerPreview,
      },
    }),
    [
      appPage,
      ree,
      locked,
      repoMode,
      actionStates,
      badges,
      timestamps,
      serviceLogs,
      serviceParams,
      toast,
      explorerPage,
      focusedField,
      navCollapsed,
      virtualFiles,
      immutableSourceSnapshotFiles,
      immutableSourceSnapshotArchiveName,
      showReviewerPreview,
    ],
  );

  const value = useMemo(
    () => ({
      state,
      setAppPage,
      setRee,
      setLocked,
      setRepoMode,
      setActionStates,
      setBadges,
      setTimestamps,
      setServiceLogs,
      setServiceParams,
      setToast,
      setExplorerPage,
      setFocusedField,
      setNavCollapsed,
      setVirtualFiles,
      setImmutableSourceSnapshotFiles,
      setImmutableSourceSnapshotArchiveName,
      setShowReviewerPreview,
    }),
    [state, setExplorerPage],
  );

  return <AppContext.Provider value={value}>{children}</AppContext.Provider>;
}

export function useAppContext(): AppContextValue {
  const ctx = useContext(AppContext);
  if (!ctx) {
    throw new Error("useAppContext must be used within AppProvider");
  }
  return ctx;
}
