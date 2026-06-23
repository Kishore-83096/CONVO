import { apiRequest } from "@/api/client"
import type {
  AddContactRequest,
  ContactDetail,
  ContactSearchRequest,
  ContactSearchResult,
  ContactSummary,
  RenameContactRequest,
} from "@/app/parrot_identity/contacts/contacts.types"

export function searchContact(
  request: ContactSearchRequest,
  accessToken: string,
) {
  return apiRequest<ContactSearchResult>(
    "/contacts/search",
    {
      method: "POST",
      body: JSON.stringify(request),
    },
    accessToken,
  )
}

export function addContact(request: AddContactRequest, accessToken: string) {
  return apiRequest<ContactDetail>(
    "/contacts",
    {
      method: "POST",
      body: JSON.stringify(request),
    },
    accessToken,
  )
}

export function listContacts(accessToken: string) {
  return apiRequest<ContactSummary[]>("/contacts", {}, accessToken)
}

export function getContact(contactId: number, accessToken: string) {
  return apiRequest<ContactDetail>(`/contacts/${contactId}`, {}, accessToken)
}

export function renameContact(
  contactId: number,
  request: RenameContactRequest,
  accessToken: string,
) {
  return apiRequest<ContactDetail>(
    `/contacts/${contactId}`,
    {
      method: "PATCH",
      body: JSON.stringify(request),
    },
    accessToken,
  )
}

export function deleteContact(contactId: number, accessToken: string) {
  return apiRequest<never>(
    `/contacts/${contactId}`,
    { method: "DELETE" },
    accessToken,
  )
}
