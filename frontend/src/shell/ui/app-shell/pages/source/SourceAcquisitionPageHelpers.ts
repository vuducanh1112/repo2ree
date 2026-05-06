export const SOURCE_TYPE_OPTIONS = ["git", "hg", "svn", "cvs", "bzr", "tarball", "zip"] as const;
export type SourceTypeOption = (typeof SOURCE_TYPE_OPTIONS)[number];
