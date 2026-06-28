export interface ProfilePicture {
  url: string
  format: string | null
  width: number | null
  height: number | null
  bytes: number | null
  created_at: string
  updated_at: string
}

export interface ContactSearchResult {
  full_name: string
  username: string
  profile_picture: ProfilePicture | null
}

export interface ContactSummary {
  id: number
  contact_user_id: number
  saved_name: string
  profile_picture: ProfilePicture | null
}

export interface ContactDetail {
  id: number
  contact_user_id: number
  saved_name: string
  contact_number: number
  username: string
  full_name: string
  profile_picture: ProfilePicture | null
}

export interface ContactSearchRequest {
  contact_number: string | number
}

export interface AddContactRequest extends ContactSearchRequest {
  saved_name: string
}

export interface RenameContactRequest {
  saved_name: string
}
