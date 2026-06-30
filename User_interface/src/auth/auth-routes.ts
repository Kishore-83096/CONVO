import type { AuthSession } from "./auth-types";

export function userHomePath(session: AuthSession | null | undefined) {
  return session?.user.username ? `/${session.user.username}` : "/login";
}

export function userWorkspacePath(
  session: AuthSession | null | undefined,
  section: "contacts" | "profile" | "settings",
) {
  const homePath = userHomePath(session);

  return homePath === "/login" ? homePath : `${homePath}/${section}`;
}
