import { identityRequest } from "../../shared/api/identityClient";

import type {
  AddContactFormValues,
  ContactSearchFormValues,
  GhostContactFormValues,
  RenameContactFormValues,
} from "./schemas";
import type {
  ContactDetail,
  ContactListResponse,
  ContactSearchResult,
  ContactSummary,
} from "./types";

export type ContactSearchPayload = {
  contact_number: string;
};

export type AddContactPayload = {
  contact_number: string;
  saved_name: string;
};

export type RenameContactPayload = {
  saved_name: string;
};

export type UpdateContactBlockPayload = {
  is_blocked: boolean;
};

export type UpdateContactGhostPayload = {
  is_ghosted: boolean;
  duration?: "1h" | "6h" | "12h" | "24h" | "permanent";
};

function cleanContactNumber(value: string) {
  return value.trim();
}

export function searchContactByNumber(
  data: ContactSearchPayload | ContactSearchFormValues,
) {
  return identityRequest<ContactSearchResult>({
    method: "POST",
    url: "/contacts/search",
    data: {
      contact_number: cleanContactNumber(data.contact_number),
    },
  });
}

export function addContact(data: AddContactPayload | AddContactFormValues) {
  return identityRequest<ContactSummary>({
    method: "POST",
    url: "/contacts",
    data: {
      contact_number: cleanContactNumber(data.contact_number),
      saved_name: data.saved_name.trim(),
    },
  });
}

export function getContacts() {
  return identityRequest<ContactListResponse>({
    method: "GET",
    url: "/contacts",
  });
}

export function getContactDetail(contactId: string) {
  return identityRequest<ContactDetail>({
    method: "GET",
    url: `/contacts/${contactId}`,
  });
}

export function renameContact(
  contactId: string,
  data: RenameContactPayload | RenameContactFormValues,
) {
  return identityRequest<ContactDetail>({
    method: "PATCH",
    url: `/contacts/${contactId}`,
    data: {
      saved_name: data.saved_name.trim(),
    },
  });
}

export function updateContactBlock(
  contactId: string,
  data: UpdateContactBlockPayload,
) {
  return identityRequest<ContactDetail>({
    method: "PATCH",
    url: `/contacts/${contactId}/block`,
    data: {
      is_blocked: data.is_blocked,
    },
  });
}

export function updateContactGhost(
  contactId: string,
  data: UpdateContactGhostPayload | GhostContactFormValues,
) {
  const payload =
    data.is_ghosted && data.duration
      ? {
          is_ghosted: true,
          duration: data.duration,
        }
      : {
          is_ghosted: false,
        };

  return identityRequest<ContactDetail>({
    method: "PATCH",
    url: `/contacts/${contactId}/ghost`,
    data: payload,
  });
}

export function deleteContact(contactId: string) {
  return identityRequest<{ contact_id?: string | number; id?: string | number }>({
    method: "DELETE",
    url: `/contacts/${contactId}`,
  });
}