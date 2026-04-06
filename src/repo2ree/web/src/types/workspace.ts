export interface FileTreeNode {
  id: string;
  name: string;
  type: "file" | "folder";
  content?: string;
  size?: number;
  tag?: string;
  children?: FileTreeNode[];
}
