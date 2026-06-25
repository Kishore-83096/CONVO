export interface Identity {
  full_name: string
  username: string
  email: string
  contact_number: number
}

export interface ProfilePicture {
  url: string
  format: string | null
  width: number | null
  height: number | null
  bytes: number | null
  created_at: string
  updated_at: string
}

export interface BasicProfile {
  bio: string | null
  date_of_birth: string | null
  gender: string | null
  occupation: string | null
  website: string | null
  created_at: string
  updated_at: string
}

export interface ProfileAddress {
  address_line_1: string
  address_line_2: string | null
  city: string
  state: string | null
  postal_code: string | null
  country: string
  created_at: string
  updated_at: string
}

export interface ProfileEvent {
  id: number
  event_name: string
  event_date: string
  description: string | null
  recurring: boolean
  created_at: string
  updated_at: string
}

export interface CompleteProfile {
  identity: Identity
  profile_picture: ProfilePicture | null
  basic_data: BasicProfile | null
  address: ProfileAddress | null
  events: ProfileEvent[]
}

export interface BasicProfileInput {
  bio?: string | null
  date_of_birth?: string | null
  gender?: string | null
  occupation?: string | null
  website?: string | null
}

export interface AddressCreateInput {
  address_line_1: string
  address_line_2?: string | null
  city: string
  state?: string | null
  postal_code?: string | null
  country: string
}

export type AddressUpdateInput = Partial<AddressCreateInput>

export interface EventCreateInput {
  event_name: string
  event_date: string
  description?: string | null
  recurring?: boolean
}

export type EventUpdateInput = Partial<EventCreateInput>
