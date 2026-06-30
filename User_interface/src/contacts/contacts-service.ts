import { contactsApi } from "./contacts-api";

import type {
  AddContactRequest,
  BlockContactRequest,
  ContactDetail,
  ContactSummary,
  GhostContactRequest,
  RenameContactRequest,
  ResolveRecipientRequest,
  ResolveRecipientResponse,
  SearchContactRequest,
  SearchContactResponse,
} from "./contacts-types";

class ContactsService {
  async search(
    request: SearchContactRequest,
  ): Promise<SearchContactResponse> {
    const { data } =
      await contactsApi.search(request);

    if (!data) {
      throw new Error(
        "Search response did not contain contact data.",
      );
    }

    return data;
  }

  async add(
    request: AddContactRequest,
  ): Promise<ContactSummary> {
    const { data } =
      await contactsApi.add(request);

    if (!data) {
      throw new Error(
        "Add contact response did not contain contact data.",
      );
    }

    return data;
  }

  async list(): Promise<ContactSummary[]> {
    const { data } =
      await contactsApi.list();

    return data ?? [];
  }

  async detail(
    contactId: number,
  ): Promise<ContactDetail> {
    const { data } =
      await contactsApi.detail(contactId);

    if (!data) {
      throw new Error(
        "Contact detail response did not contain contact data.",
      );
    }

    return data;
  }

  async rename(
    contactId: number,
    request: RenameContactRequest,
  ): Promise<ContactSummary> {
    const { data } =
      await contactsApi.rename(
        contactId,
        request,
      );

    if (!data) {
      throw new Error(
        "Rename contact response did not contain contact data.",
      );
    }

    return data;
  }

  async block(
    contactId: number,
    request: BlockContactRequest,
  ): Promise<ContactDetail> {
    const { data } =
      await contactsApi.block(
        contactId,
        request,
      );

    if (!data) {
      throw new Error(
        "Block contact response did not contain contact data.",
      );
    }

    return data;
  }

  async ghost(
    contactId: number,
    request: GhostContactRequest,
  ): Promise<ContactDetail> {
    const { data } =
      await contactsApi.ghost(
        contactId,
        request,
      );

    if (!data) {
      throw new Error(
        "Ghost contact response did not contain contact data.",
      );
    }

    return data;
  }

  async remove(
    contactId: number,
  ): Promise<void> {
    await contactsApi.remove(contactId);
  }

  async resolveRecipient(
    request: ResolveRecipientRequest,
  ): Promise<ResolveRecipientResponse> {
    const { data } =
      await contactsApi.resolveRecipient(
        request,
      );

    if (!data) {
      throw new Error(
        "Resolve recipient response did not contain recipient data.",
      );
    }

    return data;
  }
}

export const contactsService =
  new ContactsService();