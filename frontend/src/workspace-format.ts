export const workspaceExtensions = ["timescope", "chronoscope"] as const;

export function isWorkspacePath(path: string): boolean {
  const extension = /\.([^./\\]+)$/.exec(path)?.[1].toLowerCase();
  return workspaceExtensions.some((suffix) => suffix === extension);
}

export function workspaceSavePath(path: string): string {
  return isWorkspacePath(path) || /\.json$/i.test(path)
    ? path
    : path + ".timescope";
}
