export interface FileTreeNode {
  id: string;
  name: string;
  type: "file" | "folder";
  content?: string;
  tag?: string;
  children?: FileTreeNode[];
}
