import type { AuthSession } from "@/app/identity/auth/auth-session"

export function userHomePath(session: AuthSession | null) {
  const username = session?.user.username?.trim()

  return username ? `/${encodeURIComponent(username)}` : "/"
}
