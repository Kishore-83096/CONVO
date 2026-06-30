import {
  MessageCircle,
  Pencil,
  Trash2,
} from "lucide-react";
import {
  type FormEvent,
  useEffect,
  useState,
} from "react";
import {
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";

import { isApiError } from "@/api/api-errors";
import { Button, Dialog, Input } from "@/components/ui";

import { useContacts } from "./use-contacts";

import type {
  ContactDetail,
  GhostContactRequest,
  ResolveRecipientResponse,
} from "./contacts-types";

interface ContactDetailDrawerProps {
  open: boolean;
  contactId: number | null;
  onClose(): void;
}

type GhostDuration = NonNullable<GhostContactRequest["duration"]>;

export function ContactDetailDrawer({
  open,
  contactId,
  onClose,
}: ContactDetailDrawerProps) {
  const queryClient = useQueryClient();
  const {
    detail,
    rename,
    block,
    unblock,
    ghost,
    unghost,
    remove,
    resolveRecipient,
  } = useContacts();

  const [savedName, setSavedName] = useState("");
  const [ghostDuration, setGhostDuration] =
    useState<GhostDuration>("24h");
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [resolvedRecipient, setResolvedRecipient] =
    useState<ResolveRecipientResponse | null>(null);

  const detailQuery = useQuery({
    queryKey: ["contacts", "detail", contactId],
    queryFn: async () => {
      if (!contactId) {
        throw new Error("No contact selected.");
      }

      return detail(contactId);
    },
    enabled: open && contactId !== null,
  });

  const contact = detailQuery.data ?? null;
  const policy = contact?.delivery_policy;
  const isBlocked = Boolean(policy?.is_blocked);
  const isGhosted = Boolean(policy?.is_ghosted);

  useEffect(() => {
    if (contact) {
      setSavedName(contact.saved_name);
      setGhostDuration(
        contact.delivery_policy?.ghost_duration_option ?? "24h",
      );
    }
  }, [contact]);

  useEffect(() => {
    if (!open) {
      setMessage(null);
      setError(null);
      setResolvedRecipient(null);
    }
  }, [open]);

  const invalidateContacts = async () => {
    await Promise.all([
      queryClient.invalidateQueries({
        queryKey: ["contacts", "list"],
      }),
      queryClient.invalidateQueries({
        queryKey: ["contacts", "detail", contactId],
      }),
    ]);
  };

  const renameMutation = useMutation({
    mutationFn: async () => {
      if (!contactId) {
        throw new Error("No contact selected.");
      }

      return rename(contactId, {
        saved_name: savedName.trim(),
      });
    },
    onSuccess: async (updatedContact) => {
      setMessage("Contact name updated.");
      setError(null);
      queryClient.setQueryData(
        ["contacts", "detail", contactId],
        updatedContact,
      );
      await invalidateContacts();
    },
    onError: (mutationError) => {
      setMessage(null);
      setError(errorMessage(mutationError));
    },
  });

  const blockMutation = useMutation({
    mutationFn: async () => {
      if (!contactId) {
        throw new Error("No contact selected.");
      }

      return block(contactId, {
        is_blocked: true,
      });
    },
    onSuccess: async (updatedContact) => {
      setMessage(
        updatedContact.delivery_policy?.is_blocked
          ? "Contact blocked."
          : "Contact unblocked.",
      );
      setError(null);
      queryClient.setQueryData(
        ["contacts", "detail", contactId],
        updatedContact,
      );
      await invalidateContacts();
    },
    onError: (mutationError) => {
      setMessage(null);
      setError(errorMessage(mutationError));
    },
  });

  const unblockMutation = useMutation({
    mutationFn: async () => {
      if (!contactId) {
        throw new Error("No contact selected.");
      }

      return unblock(contactId);
    },
    onSuccess: async (updatedContact) => {
      setMessage("Contact unblocked.");
      setError(null);
      queryClient.setQueryData(
        ["contacts", "detail", contactId],
        updatedContact,
      );
      await invalidateContacts();
    },
    onError: (mutationError) => {
      setMessage(null);
      setError(errorMessage(mutationError));
    },
  });

  const ghostMutation = useMutation({
    mutationFn: async (payload: GhostContactRequest) => {
      if (!contactId) {
        throw new Error("No contact selected.");
      }

      return ghost(contactId, payload);
    },
    onSuccess: async (updatedContact) => {
      setMessage(
        updatedContact.delivery_policy?.is_ghosted
          ? "Contact ghosted."
          : "Contact unghosted.",
      );
      setError(null);
      queryClient.setQueryData(
        ["contacts", "detail", contactId],
        updatedContact,
      );
      await invalidateContacts();
    },
    onError: (mutationError) => {
      setMessage(null);
      setError(errorMessage(mutationError));
    },
  });

  const unghostMutation = useMutation({
    mutationFn: async () => {
      if (!contactId) {
        throw new Error("No contact selected.");
      }

      return unghost(contactId);
    },
    onSuccess: async (updatedContact) => {
      setMessage("Contact unghosted.");
      setError(null);
      queryClient.setQueryData(
        ["contacts", "detail", contactId],
        updatedContact,
      );
      await invalidateContacts();
    },
    onError: (mutationError) => {
      setMessage(null);
      setError(errorMessage(mutationError));
    },
  });

  const deleteMutation = useMutation({
    mutationFn: async () => {
      if (!contactId) {
        throw new Error("No contact selected.");
      }

      await remove(contactId);
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({
        queryKey: ["contacts", "list"],
      });
      onClose();
    },
    onError: (mutationError) => {
      setMessage(null);
      setError(errorMessage(mutationError));
    },
  });

  const resolveMutation = useMutation({
    mutationFn: async () => {
      if (!contactId) {
        throw new Error("No contact selected.");
      }

      return resolveRecipient({
        contact_id: contactId,
      });
    },
    onSuccess: (recipient) => {
      setResolvedRecipient(recipient);
      setMessage("Message recipient resolved.");
      setError(null);
    },
    onError: (mutationError) => {
      setMessage(null);
      setError(errorMessage(mutationError));
    },
  });

  function handleRename(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (savedName.trim().length === 0) {
      setError("Saved name is required.");
      return;
    }

    renameMutation.mutate();
  }

  function handleDelete() {
    if (
      window.confirm(
        "Delete this contact from your saved contacts?",
      )
    ) {
      deleteMutation.mutate();
    }
  }

  return (
    <Dialog
      open={open}
      title="Contact"
      onClose={onClose}
      width={560}
    >
      {detailQuery.isLoading && (
        <p className="sidebar-state">Loading contact...</p>
      )}

      {detailQuery.isError && (
        <div className="contacts-error">
          {errorMessage(detailQuery.error)}
        </div>
      )}

      {contact && (
        <div className="contact-detail">
          <ContactHeader contact={contact} />

          <Feedback message={message} error={error} />

          <form
            className="contact-detail__rename"
            onSubmit={handleRename}
          >
            <Input
              label="Saved name"
              value={savedName}
              maxLength={100}
              onChange={(event) =>
                setSavedName(event.target.value)
              }
              fullWidth
            />

            <Button
              type="submit"
              leftIcon={<Pencil size={15} />}
              loading={renameMutation.isPending}
            >
              Save Name
            </Button>
          </form>

          <dl className="contact-detail__facts">
            <div>
              <dt>Full name</dt>
              <dd>{contact.full_name}</dd>
            </div>
            <div>
              <dt>Username</dt>
              <dd>@{contact.username}</dd>
            </div>
            <div>
              <dt>Contact number</dt>
              <dd>{contact.contact_number}</dd>
            </div>
          </dl>

          <div className="contact-policy">
            <div className="contact-policy__row">
              <div>
                <strong>Block</strong>
                <span>{isBlocked ? "On" : "Off"}</span>
              </div>

              <PolicySwitch
                checked={isBlocked}
                disabled={
                  blockMutation.isPending ||
                  unblockMutation.isPending
                }
                label="Block contact"
                onChange={(checked) =>
                  checked
                    ? blockMutation.mutate()
                    : unblockMutation.mutate()
                }
              />
            </div>

            <div className="contact-policy__row">
              <div>
                <strong>Ghost</strong>
                <span>{ghostStatus(contact)}</span>
              </div>

              <div className="contact-policy__controls">
                <select
                  className="contact-select"
                  value={ghostDuration}
                  onChange={(event) =>
                    setGhostDuration(event.target.value as GhostDuration)
                  }
                  disabled={
                    isGhosted ||
                    ghostMutation.isPending ||
                    unghostMutation.isPending
                  }
                >
                  <option value="1h">1 hour</option>
                  <option value="6h">6 hours</option>
                  <option value="12h">12 hours</option>
                  <option value="24h">24 hours</option>
                  <option value="permanent">Permanent</option>
                </select>

                <PolicySwitch
                  checked={isGhosted}
                  disabled={
                    ghostMutation.isPending ||
                    unghostMutation.isPending
                  }
                  label="Ghost contact"
                  onChange={(checked) =>
                    checked
                      ? ghostMutation.mutate({
                          is_ghosted: true,
                          duration: ghostDuration,
                        })
                      : unghostMutation.mutate()
                  }
                />
              </div>
            </div>
          </div>

          {policy && (
            <p className="contact-detail__policy-note">
              Policy version {policy.policy_version}
              {policy.updated_at
                ? `, updated ${formatDateTime(policy.updated_at)}`
                : ""}
            </p>
          )}

          {resolvedRecipient && (
            <div className="contact-recipient">
              <strong>Recipient ID</strong>
              <span>{resolvedRecipient.contact_user_id}</span>
            </div>
          )}

          <div className="contact-detail__actions">
            <Button
              type="button"
              variant="secondary"
              leftIcon={<MessageCircle size={15} />}
              loading={resolveMutation.isPending}
              onClick={() => resolveMutation.mutate()}
            >
              Resolve Recipient
            </Button>

            <Button
              type="button"
              variant="danger"
              leftIcon={<Trash2 size={15} />}
              loading={deleteMutation.isPending}
              onClick={handleDelete}
            >
              Delete Contact
            </Button>
          </div>
        </div>
      )}
    </Dialog>
  );
}

function PolicySwitch({
  checked,
  disabled,
  label,
  onChange,
}: {
  checked: boolean;
  disabled?: boolean;
  label: string;
  onChange(checked: boolean): void;
}) {
  return (
    <label className="policy-switch">
      <input
        type="checkbox"
        role="switch"
        checked={checked}
        disabled={disabled}
        aria-label={label}
        onChange={(event) => onChange(event.target.checked)}
      />
      <span aria-hidden="true" />
    </label>
  );
}

function ContactHeader({
  contact,
}: {
  contact: ContactDetail;
}) {
  return (
    <div className="contact-detail__header">
      <span className="contacts-avatar contacts-avatar--large">
        {contact.profile_picture?.url ? (
          <img src={contact.profile_picture.url} alt="" />
        ) : (
          contact.saved_name.charAt(0).toUpperCase()
        )}
      </span>

      <div>
        <h3>{contact.saved_name}</h3>
        <p>@{contact.username}</p>
      </div>
    </div>
  );
}

function Feedback({
  message,
  error,
}: {
  message: string | null;
  error: string | null;
}) {
  if (error) {
    return <div className="contacts-error">{error}</div>;
  }

  if (message) {
    return <div className="contacts-success">{message}</div>;
  }

  return null;
}

function ghostStatus(contact: ContactDetail): string {
  const policy = contact.delivery_policy;

  if (!policy?.is_ghosted) {
    return "Off";
  }

  if (policy.ghost_permanent) {
    return "Permanent";
  }

  if (policy.ghost_until) {
    return `Until ${formatDateTime(policy.ghost_until)}`;
  }

  return "On";
}

function formatDateTime(value: string): string {
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

function errorMessage(error: unknown): string {
  if (isApiError(error) || error instanceof Error) {
    return error.message;
  }

  return "Contact request failed.";
}
