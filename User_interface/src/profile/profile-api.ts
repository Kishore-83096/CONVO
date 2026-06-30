import identityClient from "@/api/identity-client";
import { request } from "@/api/http-client";

import type {
  ApiEnvelope,
  IdentityUser,
} from "@/api/api-types";

export type ProfilePicture = {
  url: string;
  format: string;
  width: number;
  height: number;
  bytes: number;
  created_at: string;
  updated_at: string;
} | null;

export interface BasicProfile {
  bio: string | null;
  date_of_birth: string | null;
  gender: string | null;
  occupation: string | null;
  website: string | null;
  created_at: string | null;
  updated_at: string | null;
}

export interface BasicProfilePayload {
  bio?: string | null;
  date_of_birth?: string | null;
  gender?: string | null;
  occupation?: string | null;
  website?: string | null;
}

export interface ProfileAddress {
  address_line_1: string;
  address_line_2: string | null;
  city: string;
  state: string | null;
  postal_code: string | null;
  country: string;
  created_at: string | null;
  updated_at: string | null;
}

export interface AddressPayload {
  address_line_1?: string | null;
  address_line_2?: string | null;
  city?: string | null;
  state?: string | null;
  postal_code?: string | null;
  country?: string | null;
}

export interface ProfileEvent {
  id: number;
  event_name: string;
  event_date: string;
  description: string | null;
  recurring: boolean;
  created_at: string | null;
  updated_at: string | null;
}

export interface EventPayload {
  event_name?: string;
  event_date?: string;
  description?: string | null;
  recurring?: boolean;
}

export interface CompleteProfile {
  identity: IdentityUser;
  profile_picture: ProfilePicture;
  basic_data: BasicProfile | null;
  address: ProfileAddress | null;
  events: ProfileEvent[];
}

function imageFormData(image: File): FormData {
  const formData = new FormData();
  formData.append("image", image);
  return formData;
}

export const profileApi = {
  complete() {
    return request<ApiEnvelope<CompleteProfile>>(
      identityClient,
      {
        method: "GET",
        url: "/profiles/me",
      },
    );
  },

  getBasic() {
    return request<ApiEnvelope<BasicProfile>>(
      identityClient,
      {
        method: "GET",
        url: "/profiles/me/basic",
      },
    );
  },

  createBasic(payload: BasicProfilePayload) {
    return request<ApiEnvelope<BasicProfile>>(
      identityClient,
      {
        method: "POST",
        url: "/profiles/me/basic",
        data: payload,
      },
    );
  },

  patchBasic(payload: BasicProfilePayload) {
    return request<ApiEnvelope<BasicProfile>>(
      identityClient,
      {
        method: "PATCH",
        url: "/profiles/me/basic",
        data: payload,
      },
    );
  },

  putBasic(payload: BasicProfilePayload) {
    return request<ApiEnvelope<BasicProfile>>(
      identityClient,
      {
        method: "PUT",
        url: "/profiles/me/basic",
        data: payload,
      },
    );
  },

  deleteBasic() {
    return request<ApiEnvelope<null>>(
      identityClient,
      {
        method: "DELETE",
        url: "/profiles/me/basic",
      },
    );
  },

  getAddress() {
    return request<ApiEnvelope<ProfileAddress>>(
      identityClient,
      {
        method: "GET",
        url: "/profiles/me/address",
      },
    );
  },

  createAddress(payload: AddressPayload) {
    return request<ApiEnvelope<ProfileAddress>>(
      identityClient,
      {
        method: "POST",
        url: "/profiles/me/address",
        data: payload,
      },
    );
  },

  patchAddress(payload: AddressPayload) {
    return request<ApiEnvelope<ProfileAddress>>(
      identityClient,
      {
        method: "PATCH",
        url: "/profiles/me/address",
        data: payload,
      },
    );
  },

  putAddress(payload: AddressPayload) {
    return request<ApiEnvelope<ProfileAddress>>(
      identityClient,
      {
        method: "PUT",
        url: "/profiles/me/address",
        data: payload,
      },
    );
  },

  deleteAddress() {
    return request<ApiEnvelope<null>>(
      identityClient,
      {
        method: "DELETE",
        url: "/profiles/me/address",
      },
    );
  },

  listEvents() {
    return request<ApiEnvelope<ProfileEvent[]>>(
      identityClient,
      {
        method: "GET",
        url: "/profiles/me/events",
      },
    );
  },

  createEvent(payload: EventPayload) {
    return request<ApiEnvelope<ProfileEvent>>(
      identityClient,
      {
        method: "POST",
        url: "/profiles/me/events",
        data: payload,
      },
    );
  },

  getEvent(eventId: number) {
    return request<ApiEnvelope<ProfileEvent>>(
      identityClient,
      {
        method: "GET",
        url: `/profiles/me/events/${eventId}`,
      },
    );
  },

  patchEvent(
    eventId: number,
    payload: EventPayload,
  ) {
    return request<ApiEnvelope<ProfileEvent>>(
      identityClient,
      {
        method: "PATCH",
        url: `/profiles/me/events/${eventId}`,
        data: payload,
      },
    );
  },

  putEvent(eventId: number, payload: EventPayload) {
    return request<ApiEnvelope<ProfileEvent>>(
      identityClient,
      {
        method: "PUT",
        url: `/profiles/me/events/${eventId}`,
        data: payload,
      },
    );
  },

  deleteEvent(eventId: number) {
    return request<ApiEnvelope<null>>(
      identityClient,
      {
        method: "DELETE",
        url: `/profiles/me/events/${eventId}`,
      },
    );
  },

  getPicture() {
    return request<ApiEnvelope<ProfilePicture>>(
      identityClient,
      {
        method: "GET",
        url: "/profiles/me/picture",
      },
    );
  },

  createPicture(image: File) {
    return request<ApiEnvelope<ProfilePicture>>(
      identityClient,
      {
        method: "POST",
        url: "/profiles/me/picture",
        data: imageFormData(image),
      },
    );
  },

  patchPicture(image: File) {
    return request<ApiEnvelope<ProfilePicture>>(
      identityClient,
      {
        method: "PATCH",
        url: "/profiles/me/picture",
        data: imageFormData(image),
      },
    );
  },

  putPicture(image: File) {
    return request<ApiEnvelope<ProfilePicture>>(
      identityClient,
      {
        method: "PUT",
        url: "/profiles/me/picture",
        data: imageFormData(image),
      },
    );
  },

  deletePicture() {
    return request<ApiEnvelope<null>>(
      identityClient,
      {
        method: "DELETE",
        url: "/profiles/me/picture",
      },
    );
  },
};
