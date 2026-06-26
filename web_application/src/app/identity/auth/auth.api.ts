import { apiRequest } from "@/api/client"
import { clearAuthSession } from "@/app/identity/auth/auth-session"
import type {
  AccountCredentialsRequest,
  LoginData,
  LoginRequest,
  RegisteredUser,
  RegisterRequest,
  ResetPasswordRequest,
} from "@/app/identity/auth/auth.types"

export function registerAccount(request: RegisterRequest) {
  return apiRequest<RegisteredUser>("/auth/register", {
    method: "POST",
    body: JSON.stringify(request),
  })
}

export function login(request: LoginRequest) {
  return apiRequest<LoginData>("/auth/login", {
    method: "POST",
    body: JSON.stringify(request),
  })
}

export async function resetPassword(
  request: ResetPasswordRequest,
  accessToken: string,
) {
  const response = await apiRequest<never>(
    "/auth/reset-password",
    {
      method: "POST",
      body: JSON.stringify(request),
    },
    accessToken,
  )

  clearAuthSession()
  return response
}

export async function deleteAccount(
  request: AccountCredentialsRequest,
  accessToken: string,
) {
  const response = await apiRequest<never>(
    "/auth/delete-account",
    {
      method: "DELETE",
      body: JSON.stringify(request),
    },
    accessToken,
  )

  clearAuthSession()
  return response
}

export async function logout(accessToken: string) {
  const response = await apiRequest<never>(
    "/auth/logout",
    { method: "POST" },
    accessToken,
  )

  clearAuthSession()
  return response
}
