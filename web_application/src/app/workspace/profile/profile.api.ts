import { apiRequest } from "@/api/client"
import type {
  AddressCreateInput,
  AddressUpdateInput,
  BasicProfile,
  BasicProfileInput,
  CompleteProfile,
  EventCreateInput,
  EventUpdateInput,
  ProfileAddress,
  ProfileEvent,
  ProfilePicture,
} from "@/app/workspace/profile/profile.types"

export function getProfile(accessToken: string) {
  return apiRequest<CompleteProfile>("/profiles/me", {}, accessToken)
}

export function createBasicProfile(
  request: BasicProfileInput,
  accessToken: string,
) {
  return apiRequest<BasicProfile>(
    "/profiles/me/basic",
    {
      method: "POST",
      body: JSON.stringify(request),
    },
    accessToken,
  )
}

export function updateBasicProfile(
  request: BasicProfileInput,
  accessToken: string,
) {
  return apiRequest<BasicProfile>(
    "/profiles/me/basic",
    {
      method: "PATCH",
      body: JSON.stringify(request),
    },
    accessToken,
  )
}

export function deleteBasicProfile(accessToken: string) {
  return apiRequest<never>(
    "/profiles/me/basic",
    { method: "DELETE" },
    accessToken,
  )
}

export function createAddress(
  request: AddressCreateInput,
  accessToken: string,
) {
  return apiRequest<ProfileAddress>(
    "/profiles/me/address",
    {
      method: "POST",
      body: JSON.stringify(request),
    },
    accessToken,
  )
}

export function updateAddress(
  request: AddressUpdateInput,
  accessToken: string,
) {
  return apiRequest<ProfileAddress>(
    "/profiles/me/address",
    {
      method: "PATCH",
      body: JSON.stringify(request),
    },
    accessToken,
  )
}

export function deleteAddress(accessToken: string) {
  return apiRequest<never>(
    "/profiles/me/address",
    { method: "DELETE" },
    accessToken,
  )
}

export function createEvent(request: EventCreateInput, accessToken: string) {
  return apiRequest<ProfileEvent>(
    "/profiles/me/events",
    {
      method: "POST",
      body: JSON.stringify(request),
    },
    accessToken,
  )
}

export function updateEvent(
  eventId: number,
  request: EventUpdateInput,
  accessToken: string,
) {
  return apiRequest<ProfileEvent>(
    `/profiles/me/events/${eventId}`,
    {
      method: "PATCH",
      body: JSON.stringify(request),
    },
    accessToken,
  )
}

export function deleteEvent(eventId: number, accessToken: string) {
  return apiRequest<never>(
    `/profiles/me/events/${eventId}`,
    { method: "DELETE" },
    accessToken,
  )
}

export function uploadProfilePicture(
  image: File,
  hasExistingPicture: boolean,
  accessToken: string,
) {
  const formData = new FormData()
  formData.append("image", image)

  return apiRequest<ProfilePicture>(
    "/profiles/me/picture",
    {
      method: hasExistingPicture ? "PATCH" : "POST",
      body: formData,
    },
    accessToken,
  )
}

export function deleteProfilePicture(accessToken: string) {
  return apiRequest<never>(
    "/profiles/me/picture",
    { method: "DELETE" },
    accessToken,
  )
}
