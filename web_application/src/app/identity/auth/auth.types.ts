export type LoginMethod = "username" | "email" | "contact_number"

export interface RegisteredUser {
  full_name: string
  username: string
  email: string
  contact_number: number
}

export interface LoginUser {
  full_name: string
  username: string
  email: string
  contact_number: number
}

export interface LoginData {
  access_token: string
  token_type: "Bearer"
  expires_at: string
  user: LoginUser
}

export interface RegisterRequest {
  full_name: string
  username: string
  password: string
  confirm_password: string
}

export interface LoginRequest {
  method: LoginMethod
  identifier: string | number
  password: string
}

export interface AccountCredentialsRequest {
  username: string
  email: string
  contact_number: string | number
  current_password: string
}

export interface ResetPasswordRequest extends AccountCredentialsRequest {
  new_password: string
  confirm_new_password: string
}
