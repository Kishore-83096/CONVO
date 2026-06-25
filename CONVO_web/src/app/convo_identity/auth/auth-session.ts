import type {
  LoginData,
  LoginUser,
} from "@/app/convo_identity/auth/auth.types"

const accessTokenKey = "parrot_access_token"
const tokenExpiresAtKey = "parrot_token_expires_at"
const authUserKey = "parrot_auth_user"

export interface AuthSession {
  accessToken: string
  expiresAt: string
  user: LoginUser
}

export function saveAuthSession(session: LoginData) {
  sessionStorage.setItem(accessTokenKey, session.access_token)
  sessionStorage.setItem(tokenExpiresAtKey, session.expires_at)
  sessionStorage.setItem(authUserKey, JSON.stringify(session.user))
}

export function getAccessToken() {
  return sessionStorage.getItem(accessTokenKey)
}

export function getAuthSession(): AuthSession | null {
  const accessToken = sessionStorage.getItem(accessTokenKey)
  const expiresAt = sessionStorage.getItem(tokenExpiresAtKey)
  const storedUser = sessionStorage.getItem(authUserKey)

  if (!accessToken || !expiresAt || !storedUser) {
    return null
  }

  const expirationTime = Date.parse(expiresAt)

  if (!Number.isFinite(expirationTime) || expirationTime <= Date.now()) {
    clearAuthSession()
    return null
  }

  try {
    const user = JSON.parse(storedUser) as LoginUser

    if (!user.full_name || !user.email || !user.contact_number) {
      clearAuthSession()
      return null
    }

    return { accessToken, expiresAt, user }
  } catch {
    clearAuthSession()
    return null
  }
}

export function clearAuthSession() {
  sessionStorage.removeItem(accessTokenKey)
  sessionStorage.removeItem(tokenExpiresAtKey)
  sessionStorage.removeItem(authUserKey)
}
