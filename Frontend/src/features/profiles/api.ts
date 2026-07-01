import { identityRequest } from "../../shared/api/identityClient";

import type {
  AddressProfileCreateFormValues,
  AddressProfileUpdateFormValues,
  BasicProfileCreateFormValues,
  BasicProfileUpdateFormValues,
  ProfileEventCreateFormValues,
  ProfileEventUpdateFormValues,
} from "./schemas";
import type {
  MyProfile,
  ProfileAddress,
  ProfileBasic,
  ProfileEvent,
  ProfilePicture,
} from "./types";

export type BasicProfileCreatePayload = {
  bio?: string | undefined;
  date_of_birth?: string | undefined;
  gender?: string | undefined;
  occupation?: string | undefined;
  website?: string | undefined;
};

export type BasicProfileUpdatePayload = {
  bio?: string | undefined;
  date_of_birth?: string | undefined;
  gender?: string | undefined;
  occupation?: string | undefined;
  website?: string | undefined;
};

export type AddressProfileCreatePayload = {
  address_line_1: string;
  city: string;
  country: string;
  address_line_2?: string | undefined;
  state?: string | undefined;
  postal_code?: string | undefined;
};

export type AddressProfileUpdatePayload = {
  address_line_1?: string | undefined;
  address_line_2?: string | undefined;
  city?: string | undefined;
  state?: string | undefined;
  postal_code?: string | undefined;
  country?: string | undefined;
};

export type ProfileEventCreatePayload = {
  event_name: string;
  event_date: string;
  recurring: boolean;
  description?: string | undefined;
};

export type ProfileEventUpdatePayload = {
  event_name?: string | undefined;
  event_date?: string | undefined;
  description?: string | undefined;
  recurring?: boolean | undefined;
};

export function getMyProfile() {
  return identityRequest<MyProfile>({
    method: "GET",
    url: "/profiles/me",
  });
}

export function getMyProfileBasic() {
  return identityRequest<ProfileBasic | null>({
    method: "GET",
    url: "/profiles/me/basic",
  });
}

export function createMyProfileBasic(
  data: BasicProfileCreatePayload | BasicProfileCreateFormValues,
) {
  return identityRequest<ProfileBasic>({
    method: "POST",
    url: "/profiles/me/basic",
    data,
  });
}

export function updateMyProfileBasic(
  data: BasicProfileUpdatePayload | BasicProfileUpdateFormValues,
) {
  return identityRequest<ProfileBasic>({
    method: "PATCH",
    url: "/profiles/me/basic",
    data,
  });
}

export function deleteMyProfileBasic() {
  return identityRequest<unknown>({
    method: "DELETE",
    url: "/profiles/me/basic",
  });
}

export function getMyProfileAddress() {
  return identityRequest<ProfileAddress | null>({
    method: "GET",
    url: "/profiles/me/address",
  });
}

export function createMyProfileAddress(
  data: AddressProfileCreatePayload | AddressProfileCreateFormValues,
) {
  return identityRequest<ProfileAddress>({
    method: "POST",
    url: "/profiles/me/address",
    data,
  });
}

export function updateMyProfileAddress(
  data: AddressProfileUpdatePayload | AddressProfileUpdateFormValues,
) {
  return identityRequest<ProfileAddress>({
    method: "PATCH",
    url: "/profiles/me/address",
    data,
  });
}

export function deleteMyProfileAddress() {
  return identityRequest<unknown>({
    method: "DELETE",
    url: "/profiles/me/address",
  });
}

export function getMyProfileEvents() {
  return identityRequest<ProfileEvent[]>({
    method: "GET",
    url: "/profiles/me/events",
  });
}

export function createMyProfileEvent(
  data: ProfileEventCreatePayload | ProfileEventCreateFormValues,
) {
  return identityRequest<ProfileEvent>({
    method: "POST",
    url: "/profiles/me/events",
    data,
  });
}

export function getMyProfileEvent(eventId: string) {
  return identityRequest<ProfileEvent>({
    method: "GET",
    url: `/profiles/me/events/${eventId}`,
  });
}

export function updateMyProfileEvent({
  eventId,
  data,
}: {
  eventId: string;
  data: ProfileEventUpdatePayload | ProfileEventUpdateFormValues;
}) {
  return identityRequest<ProfileEvent>({
    method: "PATCH",
    url: `/profiles/me/events/${eventId}`,
    data,
  });
}

export function deleteMyProfileEvent(eventId: string) {
  return identityRequest<unknown>({
    method: "DELETE",
    url: `/profiles/me/events/${eventId}`,
  });
}

export function getMyProfilePicture() {
  return identityRequest<ProfilePicture | null>({
    method: "GET",
    url: "/profiles/me/picture",
  });
}

export function createMyProfilePicture(data: FormData) {
  return identityRequest<ProfilePicture>({
    method: "POST",
    url: "/profiles/me/picture",
    data,
  });
}

export function updateMyProfilePicture(data: FormData) {
  return identityRequest<ProfilePicture>({
    method: "PATCH",
    url: "/profiles/me/picture",
    data,
  });
}

export function deleteMyProfilePicture() {
  return identityRequest<unknown>({
    method: "DELETE",
    url: "/profiles/me/picture",
  });
}