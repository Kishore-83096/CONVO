import type {
  LoginData,
  LoginUser,
} from "@/app/identity/auth/auth.types"

const accessTokenKey = "myna_access_token"
const tokenExpiresAtKey = "myna_token_expires_at"
const authUserKey = "myna_auth_user"

const legacyAccessTokenKey = "Myna_access_token"
const legacyTokenExpiresAtKey = "Myna_token_expires_at"
const legacyAuthUserKey = "Myna_auth_user"

export interface AuthSession {
  accessToken: string
  expiresAt: string
  user: LoginUser
}

export function saveAuthSession(session: LoginData) {
  sessionStorage.setItem(accessTokenKey, session.access_token)
  sessionStorage.setItem(tokenExpiresAtKey, session.expires_at)
  sessionStorage.setItem(authUserKey, JSON.stringify(session.user))
  removeLegacyAuthSession()
}

export function getAccessToken() {
  return getSessionItem(accessTokenKey, legacyAccessTokenKey)
}

export function getAuthSession(): AuthSession | null {
  const accessToken = getSessionItem(accessTokenKey, legacyAccessTokenKey)
  const expiresAt = getSessionItem(tokenExpiresAtKey, legacyTokenExpiresAtKey)
  const storedUser = getSessionItem(authUserKey, legacyAuthUserKey)

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

    if (!user.full_name || !user.username || !user.email || !user.contact_number) {
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
  removeLegacyAuthSession()
}

function getSessionItem(key: string, legacyKey: string) {
  const value = sessionStorage.getItem(key)

  if (value) {
    return value
  }

  const legacyValue = sessionStorage.getItem(legacyKey)

  if (legacyValue) {
    sessionStorage.setItem(key, legacyValue)
    sessionStorage.removeItem(legacyKey)
  }

  return legacyValue
}

function removeLegacyAuthSession() {
  sessionStorage.removeItem(legacyAccessTokenKey)
  sessionStorage.removeItem(legacyTokenExpiresAtKey)
  sessionStorage.removeItem(legacyAuthUserKey)
}
