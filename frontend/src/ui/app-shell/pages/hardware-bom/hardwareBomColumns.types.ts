import type React from "react";
import type {
  CPURow,
  GPURow,
  MemoryRow,
  NetworkRow,
  StorageRow,
} from "../../../../core/hbom/hardwareBomDraft";

export interface HardwareColumn<RowT> {
  key: string;
  label: string;
  width: string;
  render: (row: RowT, index: number) => React.ReactNode;
}

export interface ColumnBuilderBaseArgs {
  locked: boolean;
  inp: (locked: boolean, extra?: React.CSSProperties) => React.CSSProperties;
  selectInp: (locked: boolean, extra?: React.CSSProperties) => React.CSSProperties;
}

export interface CpuColumnsArgs extends ColumnBuilderBaseArgs {
  onFocusHardwareDescription: () => void;
  patchCpuRow: (index: number, patch: Partial<CPURow>) => void;
}

export interface GpuColumnsArgs extends ColumnBuilderBaseArgs {
  patchGpuRow: (index: number, patch: Partial<GPURow>) => void;
}

export interface MemoryColumnsArgs extends ColumnBuilderBaseArgs {
  patchMemoryRow: (index: number, patch: Partial<MemoryRow>) => void;
}

export interface StorageColumnsArgs extends ColumnBuilderBaseArgs {
  patchStorageRow: (index: number, patch: Partial<StorageRow>) => void;
}

export interface NetworkColumnsArgs extends ColumnBuilderBaseArgs {
  patchNetworkRow: (index: number, patch: Partial<NetworkRow>) => void;
}
