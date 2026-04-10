import type { ReeFile, ZipEntry } from "../types";

function _zipU32(value: number): number[] {
  return [value & 0xff, (value >> 8) & 0xff, (value >> 16) & 0xff, (value >> 24) & 0xff];
}

function _zipU16(value: number): number[] {
  return [value & 0xff, (value >> 8) & 0xff];
}

function _crc32(data: Uint8Array): number {
  let c = 0xffffffff;
  for (let i = 0; i < data.length; i++) {
    c ^= data[i];
    for (let j = 0; j < 8; j++) c = c & 1 ? (c >>> 1) ^ 0xedb88320 : c >>> 1;
  }
  return (c ^ 0xffffffff) >>> 0;
}

export function buildZipBlob(entries: ZipEntry[]): Blob {
  const enc = new TextEncoder();
  const localParts: number[] = [];
  const central: number[] = [];
  const offsets: number[] = [];
  let off = 0;

  for (const entry of entries) {
    const name = enc.encode(entry.path);
    const crc = _crc32(entry.data);
    const sz = entry.data.length;
    offsets.push(off);
    const local = [
      ..._zipU32(0x04034b50),
      ..._zipU16(20),
      ..._zipU16(0),
      ..._zipU16(0),
      ..._zipU16(0),
      ..._zipU16(0),
      ..._zipU32(crc),
      ..._zipU32(sz),
      ..._zipU32(sz),
      ..._zipU16(name.length),
      ..._zipU16(0),
      ...Array.from(name),
      ...Array.from(entry.data),
    ];
    localParts.push(...local);
    off += local.length;
  }

  for (let i = 0; i < entries.length; i++) {
    const name = enc.encode(entries[i].path);
    const crc = _crc32(entries[i].data);
    const sz = entries[i].data.length;
    central.push(
      ..._zipU32(0x02014b50),
      ..._zipU16(20),
      ..._zipU16(20),
      ..._zipU16(0),
      ..._zipU16(0),
      ..._zipU16(0),
      ..._zipU16(0),
      ..._zipU32(crc),
      ..._zipU32(sz),
      ..._zipU32(sz),
      ..._zipU16(name.length),
      ..._zipU16(0),
      ..._zipU16(0),
      ..._zipU16(0),
      ..._zipU16(0),
      ..._zipU32(0),
      ..._zipU32(offsets[i]),
      ...Array.from(name),
    );
  }

  const cdOff = off;
  const eocd = [
    ..._zipU32(0x06054b50),
    ..._zipU16(0),
    ..._zipU16(0),
    ..._zipU16(entries.length),
    ..._zipU16(entries.length),
    ..._zipU32(central.length),
    ..._zipU32(cdOff),
    ..._zipU16(0),
  ];

  return new Blob([new Uint8Array([...localParts, ...central, ...eocd])], {
    type: "application/zip",
  });
}

export const REE_ROOT_PREFIX = "ree/";
export const REE_MANIFEST_PATH = `${REE_ROOT_PREFIX}ree.json`;
export const REE_SBOM_PATH = `${REE_ROOT_PREFIX}sbom.json`;
export const REE_RUNTIME_PATH = `${REE_ROOT_PREFIX}runtime.tar.gz`;
export const REE_SOURCE_REPO_PREFIX = `${REE_ROOT_PREFIX}source-repo/`;

const REE_ARCHIVE_TAG_BY_PATH: Record<string, string> = {
  [REE_MANIFEST_PATH]: "Manifest",
  [REE_SBOM_PATH]: "SBOM",
  [REE_RUNTIME_PATH]: "Runtime",
};

function resolveReeArchiveEntryTag(path: string): string {
  const knownTag = REE_ARCHIVE_TAG_BY_PATH[path];
  if (knownTag) return knownTag;
  if (path.startsWith(REE_SOURCE_REPO_PREFIX)) return "Source";
  if (path.startsWith(REE_ROOT_PREFIX)) return "Workspace";
  return "REE";
}

export function reeArchiveEntriesToFiles(entries: ZipEntry[]): ReeFile[] {
  const dec = new TextDecoder();
  return entries.map((entry, idx) => ({
    id: `ree-archive-${idx}`,
    name: entry.path,
    type: "file",
    tag: resolveReeArchiveEntryTag(entry.path),
    size: entry.data.length,
    content: dec.decode(entry.data),
  }));
}
