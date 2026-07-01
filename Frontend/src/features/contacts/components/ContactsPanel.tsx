import { zodResolver } from "@hookform/resolvers/zod";
import { useEffect, useMemo, useState } from "react";
import { useForm } from "react-hook-form";

import { Button } from "../../../shared/ui/Button";
import { FormField } from "../../../shared/ui/FormField";
import { Input } from "../../../shared/ui/Input";
import {
  addContactSchema,
  contactSearchSchema,
  ghostContactSchema,
  ghostDurationValues,
  renameContactSchema,
  type AddContactFormValues,
  type ContactSearchFormValues,
  type GhostContactFormValues,
  type GhostDuration,
  type RenameContactFormValues,
} from "../schemas";
import {
  useAddContact,
  useContactDetail,
  useContacts,
  useDeleteContact,
  useRenameContact,
  useSearchContact,
  useUpdateContactBlock,
  useUpdateContactGhost,
} from "../hooks";
import type {
  ContactDeliveryPolicy,
  ContactDetail,
  ContactListResponse,
  ContactProfilePicture,
  ContactPublicUser,
  ContactSearchResult,
  ContactSummary,
} from "../types";

type ContactLike = ContactSummary | ContactDetail | ContactSearchResult;

function normalizeContacts(data: ContactListResponse | undefined) {
  if (!data) {
    return [];
  }

  if (Array.isArray(data)) {
    return data;
  }

  return data.contacts ?? data.results ?? data.items ?? [];
}

function toText(value: number | string | null | undefined) {
  if (value === null || value === undefined || value === "") {
    return "";
  }

  return String(value);
}

function getNestedUser(contact: ContactLike | null | undefined) {
  return (
    contact?.contact_user ??
    contact?.target_user ??
    contact?.user ??
    contact?.contact ??
    undefined
  );
}

function getContactId(contact: ContactSummary | ContactDetail | undefined) {
  return toText(contact?.id ?? contact?.contact_id);
}

function getDisplayName(
  contact: ContactLike | ContactPublicUser | null | undefined,
) {
  const nested =
    "contact_user" in (contact ?? {}) ? getNestedUser(contact as ContactLike) : null;

  return (
    contact?.saved_name ??
    contact?.full_name ??
    nested?.full_name ??
    contact?.username ??
    nested?.username ??
    "Unnamed contact"
  );
}

function getUsername(contact: ContactLike | ContactPublicUser | null | undefined) {
  const nested =
    "contact_user" in (contact ?? {}) ? getNestedUser(contact as ContactLike) : null;

  return contact?.username ?? nested?.username ?? "";
}

function getContactNumber(
  contact: ContactLike | ContactPublicUser | null | undefined,
) {
  const nested =
    "contact_user" in (contact ?? {}) ? getNestedUser(contact as ContactLike) : null;

  return toText(contact?.contact_number ?? nested?.contact_number);
}

function getPicture(contact: ContactLike | ContactPublicUser | null | undefined) {
  const nested =
    "contact_user" in (contact ?? {}) ? getNestedUser(contact as ContactLike) : null;

  return (
    contact?.profile_picture ??
    contact?.picture ??
    nested?.profile_picture ??
    nested?.picture ??
    null
  );
}

function getPictureUrl(picture: ContactProfilePicture | null | undefined) {
  return (
    picture?.secure_url ??
    picture?.image_url ??
    picture?.url ??
    picture?.picture_url ??
    picture?.profile_picture_url ??
    picture?.cloudinary_url ??
    picture?.file_url ??
    picture?.image ??
    ""
  );
}

function getInitials(name: string) {
  return name
    .trim()
    .split(/\s+/)
    .map((part) => part[0])
    .join("")
    .slice(0, 2)
    .toUpperCase();
}

function getDeliveryPolicy(contact: ContactDetail | ContactSummary | undefined) {
  return contact?.delivery_policy ?? contact?.policy ?? null;
}

function formatDateTime(value: string | null | undefined) {
  if (!value) {
    return "—";
  }

  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return date.toLocaleString();
}

function renderPolicyValue(value: boolean | number | string | null | undefined) {
  if (value === true) {
    return "Yes";
  }

  if (value === false) {
    return "No";
  }

  return value === null || value === undefined || value === "" ? "—" : String(value);
}

function isGhostDuration(value: unknown): value is GhostDuration {
  return ghostDurationValues.includes(value as GhostDuration);
}

function ContactAvatar({ contact }: { contact: ContactLike | ContactPublicUser }) {
  const name = getDisplayName(contact);
  const pictureUrl = getPictureUrl(getPicture(contact));

  if (pictureUrl) {
    return <img alt="" className="contact-avatar contact-avatar--image" src={pictureUrl} />;
  }

  return <span className="contact-avatar">{getInitials(name) || "--"}</span>;
}

function PolicyRows({ policy }: { policy: ContactDeliveryPolicy | null }) {
  if (!policy) {
    return (
      <p className="contact-empty-note">
        No delivery policy is attached to this contact detail response yet.
      </p>
    );
  }

  return (
    <div className="health-panel contact-policy-grid">
      <div className="health-row">
        <strong>Blocked</strong>
        <span>{renderPolicyValue(policy.is_blocked)}</span>
      </div>
      <div className="health-row">
        <strong>Blocked at</strong>
        <span>{formatDateTime(policy.blocked_at)}</span>
      </div>
      <div className="health-row">
        <strong>Ghosted</strong>
        <span>{renderPolicyValue(policy.is_ghosted)}</span>
      </div>
      <div className="health-row">
        <strong>Ghost until</strong>
        <span>{formatDateTime(policy.ghost_until)}</span>
      </div>
      <div className="health-row">
        <strong>Permanent ghost</strong>
        <span>{renderPolicyValue(policy.ghost_permanent)}</span>
      </div>
      <div className="health-row">
        <strong>Ghost duration</strong>
        <span>{renderPolicyValue(policy.ghost_duration_option)}</span>
      </div>
      <div className="health-row">
        <strong>Policy version</strong>
        <span>{renderPolicyValue(policy.policy_version)}</span>
      </div>
      <div className="health-row">
        <strong>Policy updated</strong>
        <span>{formatDateTime(policy.updated_at)}</span>
      </div>
    </div>
  );
}

export function ContactsPanel() {
  const [selectedContactId, setSelectedContactId] = useState("");
  const [searchedContact, setSearchedContact] =
    useState<ContactSearchResult | null>(null);
  const [statusMessage, setStatusMessage] = useState("");

  const contactsQuery = useContacts();
  const contactDetailQuery = useContactDetail(selectedContactId);
  const searchContactMutation = useSearchContact();
  const addContactMutation = useAddContact();
  const renameContactMutation = useRenameContact();
  const blockContactMutation = useUpdateContactBlock();
  const ghostContactMutation = useUpdateContactGhost();
  const deleteContactMutation = useDeleteContact();

  const contacts = useMemo(() => {
    return contactsQuery.data?.ok
      ? normalizeContacts(contactsQuery.data.data)
      : [];
  }, [contactsQuery.data]);

  const selectedContact = contactDetailQuery.data?.ok
    ? contactDetailQuery.data.data
    : undefined;

  const selectedPolicy = getDeliveryPolicy(selectedContact);
  const selectedIsBlocked = Boolean(selectedPolicy?.is_blocked);
  const selectedIsGhosted = Boolean(selectedPolicy?.is_ghosted);

  const searchForm = useForm<ContactSearchFormValues>({
    resolver: zodResolver(contactSearchSchema),
    defaultValues: {
      contact_number: "",
    },
  });

  const addForm = useForm<AddContactFormValues>({
    resolver: zodResolver(addContactSchema),
    defaultValues: {
      contact_number: "",
      saved_name: "",
    },
  });

  const renameForm = useForm<RenameContactFormValues>({
    resolver: zodResolver(renameContactSchema),
    defaultValues: {
      saved_name: "",
    },
  });

  const ghostForm = useForm<GhostContactFormValues>({
    resolver: zodResolver(ghostContactSchema),
    defaultValues: {
      is_ghosted: false,
      duration: "24h",
    },
  });

  useEffect(() => {
    if (selectedContactId || contacts.length === 0) {
      return;
    }

    const firstContactId = getContactId(contacts[0]);

    if (firstContactId) {
      window.queueMicrotask(() => setSelectedContactId(firstContactId));
    }
  }, [contacts, selectedContactId]);

  useEffect(() => {
    if (!selectedContact) {
      renameForm.reset({ saved_name: "" });
      return;
    }

    renameForm.reset({
      saved_name: selectedContact.saved_name || getDisplayName(selectedContact),
    });
  }, [renameForm, selectedContact]);

  useEffect(() => {
    const duration = selectedPolicy?.ghost_duration_option;

    ghostForm.reset({
      is_ghosted: Boolean(selectedPolicy?.is_ghosted),
      duration: isGhostDuration(duration) ? duration : "24h",
    });
  }, [ghostForm, selectedPolicy]);

  async function handleSearch(values: ContactSearchFormValues) {
    setStatusMessage("");
    setSearchedContact(null);

    const result = await searchContactMutation.mutateAsync(values);

    if (!result.ok) {
      setStatusMessage(result.message);
      return;
    }

    setSearchedContact(result.data);
    setStatusMessage(result.message ?? "Contact found. Add a saved name to save it.");

    addForm.setValue("contact_number", values.contact_number, {
      shouldValidate: true,
    });
    addForm.setValue("saved_name", getDisplayName(result.data), {
      shouldValidate: true,
    });
  }

  async function handleAdd(values: AddContactFormValues) {
    setStatusMessage("");

    const result = await addContactMutation.mutateAsync(values);

    if (!result.ok) {
      setStatusMessage(result.message);
      return;
    }

    setStatusMessage(result.message ?? "Contact saved successfully.");
    setSearchedContact(null);
    searchForm.reset({ contact_number: "" });
    addForm.reset({ contact_number: "", saved_name: "" });

    const nextContactId = getContactId(result.data);

    if (nextContactId) {
      setSelectedContactId(nextContactId);
    }
  }

  async function handleRename(values: RenameContactFormValues) {
    if (!selectedContactId) {
      setStatusMessage("Select a contact first.");
      return;
    }

    setStatusMessage("");

    const result = await renameContactMutation.mutateAsync({
      contactId: selectedContactId,
      values,
    });

    setStatusMessage(
      result.ok ? result.message ?? "Contact renamed successfully." : result.message,
    );
  }

  async function handleBlockToggle() {
    if (!selectedContactId) {
      setStatusMessage("Select a contact first.");
      return;
    }

    const nextBlockedState = !selectedIsBlocked;

    setStatusMessage("");

    const result = await blockContactMutation.mutateAsync({
      contactId: selectedContactId,
      values: {
        is_blocked: nextBlockedState,
      },
    });

    setStatusMessage(
      result.ok
        ? result.message ??
            (nextBlockedState
              ? "Contact blocked successfully."
              : "Contact unblocked successfully.")
        : result.message,
    );
  }

  async function handleGhost(values: GhostContactFormValues) {
    if (!selectedContactId) {
      setStatusMessage("Select a contact first.");
      return;
    }

    setStatusMessage("");

    const result = await ghostContactMutation.mutateAsync({
      contactId: selectedContactId,
      values: values.is_ghosted
        ? {
            is_ghosted: true,
            duration: values.duration,
          }
        : {
            is_ghosted: false,
          },
    });

    setStatusMessage(
      result.ok
        ? result.message ??
            (values.is_ghosted
              ? "Ghost mode enabled successfully."
              : "Ghost mode disabled successfully.")
        : result.message,
    );
  }

  async function handleDelete() {
    if (!selectedContactId) {
      setStatusMessage("Select a contact first.");
      return;
    }

    const selectedName = selectedContact
      ? getDisplayName(selectedContact)
      : "this contact";

    const confirmed = window.confirm(
      `Delete ${selectedName}? This removes the saved contact from your list.`,
    );

    if (!confirmed) {
      return;
    }

    setStatusMessage("");

    const result = await deleteContactMutation.mutateAsync({
      contactId: selectedContactId,
    });

    if (!result.ok) {
      setStatusMessage(result.message);
      return;
    }

    setSelectedContactId("");
    setStatusMessage(result.message ?? "Contact deleted successfully.");
  }

  return (
    <div className="profile-workspace contacts-workspace">
      <section className="section-heading">
        <h2>Contacts</h2>
        <p>
          Search by a 10-digit contact number, save the contact with a friendly
          name, then manage rename, block, ghost, and delete actions from the
          detail panel.
        </p>
      </section>

      <div className="contacts-split-grid">
        <section className="contact-panel contact-panel--add">
          <div className="profile-detail-group-header">
            <div>
              <h3>3.1 Search contact</h3>
              <p className="contact-section-copy">
                Uses <code>POST /contacts/search</code>.
              </p>
            </div>
          </div>

          <form
            className="settings-form contact-inline-form"
            onSubmit={searchForm.handleSubmit(handleSearch)}
          >
            <FormField
              error={searchForm.formState.errors.contact_number?.message}
              hint="Example: 7467449164"
              htmlFor="contact-search-number"
              label="Contact number"
            >
              <Input
                autoComplete="off"
                hasError={Boolean(searchForm.formState.errors.contact_number)}
                id="contact-search-number"
                inputMode="numeric"
                maxLength={10}
                placeholder="10-digit number"
                {...searchForm.register("contact_number")}
              />
            </FormField>

            <div className="actions">
              <Button disabled={searchContactMutation.isPending} type="submit">
                {searchContactMutation.isPending ? "Searching..." : "Search"}
              </Button>
            </div>
          </form>

          {searchedContact ? (
            <article className="contact-search-result">
              <ContactAvatar contact={searchedContact} />
              <div>
                <strong>{getDisplayName(searchedContact)}</strong>
                <span>@{getUsername(searchedContact) || "unknown"}</span>
                <small>
                  {getContactNumber(searchedContact) || "No number returned"}
                </small>
              </div>
            </article>
          ) : null}

          <div className="profile-detail-group-header contact-add-heading">
            <div>
              <h3>3.2 Add contact</h3>
              <p className="contact-section-copy">
                Uses <code>POST /contacts</code>.
              </p>
            </div>
          </div>

          <form
            className="settings-form contact-inline-form"
            onSubmit={addForm.handleSubmit(handleAdd)}
          >
            <FormField
              error={addForm.formState.errors.contact_number?.message}
              htmlFor="contact-add-number"
              label="Contact number"
            >
              <Input
                autoComplete="off"
                hasError={Boolean(addForm.formState.errors.contact_number)}
                id="contact-add-number"
                inputMode="numeric"
                maxLength={10}
                placeholder="10-digit number"
                {...addForm.register("contact_number")}
              />
            </FormField>

            <FormField
              error={addForm.formState.errors.saved_name?.message}
              htmlFor="contact-add-saved-name"
              label="Saved name"
            >
              <Input
                autoComplete="off"
                hasError={Boolean(addForm.formState.errors.saved_name)}
                id="contact-add-saved-name"
                maxLength={100}
                placeholder="Grace"
                {...addForm.register("saved_name")}
              />
            </FormField>

            <div className="actions">
              <Button disabled={addContactMutation.isPending} type="submit">
                {addContactMutation.isPending ? "Saving..." : "Save contact"}
              </Button>
            </div>
          </form>

          {statusMessage ? (
            <p
              className={
                searchContactMutation.data?.ok ||
                addContactMutation.data?.ok ||
                renameContactMutation.data?.ok ||
                blockContactMutation.data?.ok ||
                ghostContactMutation.data?.ok ||
                deleteContactMutation.data?.ok
                  ? "auth-success"
                  : "auth-error"
              }
            >
              {statusMessage}
            </p>
          ) : null}
        </section>

        <section className="contact-panel">
          <div className="profile-detail-group-header">
            <div>
              <h3>3.3 Saved contacts</h3>
              <p className="contact-section-copy">
                Uses <code>GET /contacts</code>.
              </p>
            </div>
            <Button
              disabled={contactsQuery.isFetching}
              onClick={() => void contactsQuery.refetch()}
              type="button"
              variant="secondary"
            >
              Refresh
            </Button>
          </div>

          {contactsQuery.isLoading ? (
            <p className="contact-empty-note">Loading contacts...</p>
          ) : null}

          {contactsQuery.data && !contactsQuery.data.ok ? (
            <p className="auth-error">{contactsQuery.data.message}</p>
          ) : null}

          {!contactsQuery.isLoading && contacts.length === 0 ? (
            <p className="contact-empty-note">
              No saved contacts yet. Search a number and save the contact first.
            </p>
          ) : null}

          <div className="contact-list" aria-label="Saved contacts">
            {contacts.map((contact) => {
              const contactId = getContactId(contact);
              const isSelected = contactId === selectedContactId;

              return (
                <button
                  className={`contact-list-item ${isSelected ? "active" : ""}`}
                  disabled={!contactId}
                  key={
                    contactId ||
                    `${getDisplayName(contact)}-${getContactNumber(contact)}`
                  }
                  onClick={() => setSelectedContactId(contactId)}
                  type="button"
                >
                  <ContactAvatar contact={contact} />
                  <span className="contact-list-copy">
                    <strong>{getDisplayName(contact)}</strong>
                    <span>
                      {getUsername(contact)
                        ? `@${getUsername(contact)}`
                        : "Username not returned"}
                    </span>
                    <small>{getContactNumber(contact) || "Number not returned"}</small>
                  </span>
                </button>
              );
            })}
          </div>
        </section>

        <section className="contact-panel contact-panel--detail">
          <div className="profile-detail-group-header">
            <div>
              <h3>3.4 Contact detail</h3>
              <p className="contact-section-copy">
                Uses <code>GET /contacts/{"{contact_id}"}</code>.
              </p>
            </div>
          </div>

          {!selectedContactId ? (
            <p className="contact-empty-note">
              Select a saved contact to load full detail.
            </p>
          ) : null}

          {contactDetailQuery.isLoading ? (
            <p className="contact-empty-note">Loading contact detail...</p>
          ) : null}

          {contactDetailQuery.data && !contactDetailQuery.data.ok ? (
            <p className="auth-error">{contactDetailQuery.data.message}</p>
          ) : null}

          {selectedContact ? (
            <div className="contact-detail-card">
              <div className="contact-detail-hero">
                <ContactAvatar contact={selectedContact} />
                <div>
                  <h3>{getDisplayName(selectedContact)}</h3>
                  <p>
                    {getUsername(selectedContact)
                      ? `@${getUsername(selectedContact)}`
                      : "Username not returned"}
                  </p>
                  <small>
                    {getContactNumber(selectedContact) || "Number not returned"}
                  </small>
                </div>
              </div>

              <div className="health-panel">
                <div className="health-row">
                  <strong>Contact ID</strong>
                  <span>{selectedContactId}</span>
                </div>
                <div className="health-row">
                  <strong>Saved name</strong>
                  <span>{selectedContact.saved_name || "—"}</span>
                </div>
                <div className="health-row">
                  <strong>Created</strong>
                  <span>{formatDateTime(selectedContact.created_at)}</span>
                </div>
                <div className="health-row">
                  <strong>Updated</strong>
                  <span>{formatDateTime(selectedContact.updated_at)}</span>
                </div>
              </div>

              <section className="contact-action-card">
                <div>
                  <h4>3.5 Rename contact</h4>
                  <p>
                    Uses <code>PATCH /contacts/{"{contact_id}"}</code>.
                  </p>
                </div>

                <form
                  className="settings-form contact-inline-form"
                  onSubmit={renameForm.handleSubmit(handleRename)}
                >
                  <FormField
                    error={renameForm.formState.errors.saved_name?.message}
                    htmlFor="contact-rename-saved-name"
                    label="Saved name"
                  >
                    <Input
                      autoComplete="off"
                      hasError={Boolean(renameForm.formState.errors.saved_name)}
                      id="contact-rename-saved-name"
                      maxLength={100}
                      placeholder="Grace H."
                      {...renameForm.register("saved_name")}
                    />
                  </FormField>

                  <div className="actions">
                    <Button
                      disabled={renameContactMutation.isPending}
                      type="submit"
                    >
                      {renameContactMutation.isPending ? "Renaming..." : "Rename"}
                    </Button>
                  </div>
                </form>
              </section>

              <section className="contact-action-card">
                <div>
                  <h4>3.6 Block / unblock contact</h4>
                  <p>
                    Uses <code>PATCH /contacts/{"{contact_id}"}/block</code>.
                  </p>
                </div>

                <div className="contact-action-row">
                  <div>
                    <strong>
                      Current state: {selectedIsBlocked ? "Blocked" : "Not blocked"}
                    </strong>
                    <span>
                      Blocked contacts cannot deliver messages to you, but your
                      backend rules still allow you to send messages to them.
                    </span>
                  </div>

                  <Button
                    disabled={blockContactMutation.isPending}
                    onClick={() => void handleBlockToggle()}
                    type="button"
                    variant="secondary"
                  >
                    {blockContactMutation.isPending
                      ? "Updating..."
                      : selectedIsBlocked
                        ? "Unblock"
                        : "Block"}
                  </Button>
                </div>
              </section>

              <section className="contact-action-card">
                <div>
                  <h4>3.7 Ghost / unghost contact</h4>
                  <p>
                    Uses <code>PATCH /contacts/{"{contact_id}"}/ghost</code>.
                  </p>
                </div>

                <form
                  className="settings-form contact-inline-form"
                  onSubmit={ghostForm.handleSubmit(handleGhost)}
                >
                  <label className="contact-checkbox-row">
                    <input
                      type="checkbox"
                      {...ghostForm.register("is_ghosted")}
                    />
                    <span>Enable ghost mode for this contact</span>
                  </label>

                  <FormField
                    error={ghostForm.formState.errors.duration?.message}
                    htmlFor="contact-ghost-duration"
                    label="Ghost duration"
                  >
                    <select
                      className="contact-select"
                      id="contact-ghost-duration"
                      {...ghostForm.register("duration")}
                    >
                      <option value="1h">1 hour</option>
                      <option value="6h">6 hours</option>
                      <option value="12h">12 hours</option>
                      <option value="24h">24 hours</option>
                      <option value="permanent">Permanent</option>
                    </select>
                  </FormField>

                  <div className="actions">
                    <Button
                      disabled={ghostContactMutation.isPending}
                      type="submit"
                    >
                      {ghostContactMutation.isPending
                        ? "Updating..."
                        : selectedIsGhosted
                          ? "Update ghost"
                          : "Apply ghost"}
                    </Button>

                    {selectedIsGhosted ? (
                      <Button
                        disabled={ghostContactMutation.isPending}
                        onClick={() =>
                          void handleGhost({
                            is_ghosted: false,
                          })
                        }
                        type="button"
                        variant="secondary"
                      >
                        Unghost
                      </Button>
                    ) : null}
                  </div>
                </form>
              </section>

              <section className="contact-action-card contact-danger-zone">
                <div>
                  <h4>3.8 Delete contact</h4>
                  <p>
                    Uses <code>DELETE /contacts/{"{contact_id}"}</code>. This
                    removes the saved contact entry from your list.
                  </p>
                </div>

                <button
                  className="contact-danger-button"
                  disabled={deleteContactMutation.isPending}
                  onClick={() => void handleDelete()}
                  type="button"
                >
                  {deleteContactMutation.isPending
                    ? "Deleting..."
                    : "Delete contact"}
                </button>
              </section>

              <div className="contact-policy-heading">
                <h4>Delivery policy</h4>
                <p>
                  This policy comes from the contact detail response. Block and
                  ghost actions above should update this section after the API
                  succeeds.
                </p>
              </div>

              <PolicyRows policy={selectedPolicy} />
            </div>
          ) : null}
        </section>
      </div>
    </div>
  );
}