import { useState } from "react";
import {
  CalendarPlus,
  RefreshCw,
  Save,
  Trash2,
} from "lucide-react";
import {
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";

import Button from "@/ui/Button";
import { isApiError } from "@/api/api-errors";
import type { IdentityUser } from "@/api/api-types";

import { ProfileEditor } from "./ProfileEditor";
import { ProfilePictureUploader } from "./ProfilePictureUploader";
import {
  profileApi,
  type CompleteProfile,
  type EventPayload,
  type ProfileEvent,
} from "./profile-api";
import "./profile.css";

interface EventFormState {
  event_name: string;
  event_date: string;
  description: string;
  recurring: boolean;
}

const emptyEventForm: EventFormState = {
  event_name: "",
  event_date: "",
  description: "",
  recurring: true,
};

export function ProfilePage() {
  const profileQuery = useQuery({
    queryKey: ["profile", "complete"],
    queryFn: async () => {
      const response = await profileApi.complete();
      return response.data;
    },
  });

  const profile = profileQuery.data;

  return (
    <section className="workspace-view active">
      <header className="workspace-header">
        <div className="workspace-title-row">
          <div>
            <span className="section-kicker">Account</span>
            <h1>Profile</h1>
          </div>

          <Button
            type="button"
            variant="secondary"
            leftIcon={<RefreshCw size={16} />}
            loading={profileQuery.isFetching}
            onClick={() => {
              void profileQuery.refetch();
            }}
          >
            Refresh
          </Button>
        </div>
      </header>

      <div className="workspace-content">
        {profileQuery.isLoading && (
          <p className="sidebar-state">Loading profile...</p>
        )}

        {profileQuery.isError && (
          <div className="profile-error">
            {errorMessage(profileQuery.error)}
          </div>
        )}

        {profile && <ProfileContent profile={profile} />}
      </div>
    </section>
  );
}

function ProfileContent({
  profile,
}: {
  profile: CompleteProfile;
}) {
  const initials = makeInitials(profile.identity);

  return (
    <div className="profile-grid">
      <IdentityPanel identity={profile.identity} />

      <ProfilePictureUploader
        picture={profile.profile_picture}
        initials={initials}
      />

      <ProfileEditor
        basic={profile.basic_data}
        address={profile.address}
      />

      <EventsPanel events={profile.events} />
    </div>
  );
}

function IdentityPanel({
  identity,
}: {
  identity: IdentityUser;
}) {
  return (
    <section className="profile-panel">
      <div className="profile-panel__header">
        <div>
          <h2>Identity</h2>
          <p>Read-only account details from the identity service.</p>
        </div>
      </div>

      <dl className="profile-details">
        <div>
          <dt>Full name</dt>
          <dd>{identity.full_name}</dd>
        </div>
        <div>
          <dt>Username</dt>
          <dd>@{identity.username}</dd>
        </div>
        <div>
          <dt>Email</dt>
          <dd>{identity.email}</dd>
        </div>
        <div>
          <dt>Contact number</dt>
          <dd>{identity.contact_number}</dd>
        </div>
      </dl>
    </section>
  );
}

function EventsPanel({
  events,
}: {
  events: ProfileEvent[];
}) {
  const queryClient = useQueryClient();
  const [form, setForm] =
    useState<EventFormState>(emptyEventForm);
  const [editingId, setEditingId] = useState<number | null>(
    null,
  );
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const selectedEvent =
    editingId === null
      ? null
      : events.find((event) => event.id === editingId) ??
        null;

  const detailQuery = useQuery({
    queryKey: ["profile", "event", editingId],
    queryFn: async () => {
      if (editingId === null) {
        throw new Error("No event selected.");
      }

      const response = await profileApi.getEvent(editingId);
      return response.data;
    },
    enabled: editingId !== null,
  });

  const invalidateProfile = async () => {
    await queryClient.invalidateQueries({
      queryKey: ["profile", "complete"],
    });
  };

  const saveMutation = useMutation({
    mutationFn: (payload: EventPayload) =>
      editingId
        ? profileApi.patchEvent(editingId, payload)
        : profileApi.createEvent(payload),
    onSuccess: async (response) => {
      setMessage(response.message);
      setError(null);
      setForm(emptyEventForm);
      setEditingId(null);
      await invalidateProfile();
    },
    onError: (mutationError) => {
      setMessage(null);
      setError(errorMessage(mutationError));
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (eventId: number) =>
      profileApi.deleteEvent(eventId),
    onSuccess: async (response) => {
      setMessage(response.message);
      setError(null);
      setEditingId(null);
      setForm(emptyEventForm);
      await invalidateProfile();
    },
    onError: (mutationError) => {
      setMessage(null);
      setError(errorMessage(mutationError));
    },
  });

  function updateField(
    field: keyof EventFormState,
    value: string | boolean,
  ) {
    setForm((current) => ({
      ...current,
      [field]: value,
    }));
  }

  function startEdit(event: ProfileEvent) {
    setEditingId(event.id);
    setForm(eventToForm(event));
    setMessage(null);
    setError(null);
  }

  function resetForm() {
    setEditingId(null);
    setForm(emptyEventForm);
    setMessage(null);
    setError(null);
  }

  function handleSubmit() {
    const payload = eventPayload(form);

    if (!payload.event_name || !payload.event_date) {
      setMessage(null);
      setError("Event name and date are required.");
      return;
    }

    saveMutation.mutate(payload);
  }

  return (
    <section className="profile-panel">
      <div className="profile-panel__header">
        <div>
          <h2>Events</h2>
          <p>Manage up to five personal profile events.</p>
        </div>
        <span className="status-pill">{events.length}/5</span>
      </div>

      <Feedback message={message} error={error} />

      <div className="profile-form">
        <div className="profile-form__row">
          <label className="profile-field">
            <span>Event name</span>
            <input
              maxLength={80}
              value={form.event_name}
              onChange={(event) =>
                updateField(
                  "event_name",
                  event.target.value,
                )
              }
            />
          </label>

          <label className="profile-field">
            <span>Event date</span>
            <input
              type="date"
              value={form.event_date}
              onChange={(event) =>
                updateField(
                  "event_date",
                  event.target.value,
                )
              }
            />
          </label>
        </div>

        <label className="profile-field">
          <span>Description</span>
          <textarea
            maxLength={300}
            value={form.description}
            onChange={(event) =>
              updateField(
                "description",
                event.target.value,
              )
            }
          />
          <small>{form.description.length}/300</small>
        </label>

        <label className="profile-checkbox">
          <input
            type="checkbox"
            checked={form.recurring}
            onChange={(event) =>
              updateField("recurring", event.target.checked)
            }
          />
          Recurring event
        </label>

        {selectedEvent && detailQuery.data && (
          <p className="profile-muted">
            Editing server event #{detailQuery.data.id}, last
            updated {formatDateTime(detailQuery.data.updated_at)}.
          </p>
        )}

        <div className="profile-actions">
          {editingId !== null && (
            <Button
              type="button"
              variant="secondary"
              onClick={resetForm}
            >
              Cancel
            </Button>
          )}

          <Button
            type="button"
            leftIcon={
              editingId ? (
                <Save size={16} />
              ) : (
                <CalendarPlus size={16} />
              )
            }
            loading={saveMutation.isPending}
            onClick={handleSubmit}
          >
            {editingId ? "Save Event" : "Create Event"}
          </Button>
        </div>
      </div>

      <div className="profile-events">
        {events.length === 0 && (
          <p className="profile-muted">
            No profile events yet.
          </p>
        )}

        {events.map((event) => (
          <article className="profile-event" key={event.id}>
            <div className="profile-event__header">
              <div>
                <strong>{event.event_name}</strong>
                <span>
                  {formatDate(event.event_date)}
                  {event.recurring ? " - recurring" : ""}
                </span>
              </div>
              <div className="profile-event__actions">
                <Button
                  type="button"
                  variant="secondary"
                  size="sm"
                  onClick={() => startEdit(event)}
                >
                  Edit
                </Button>
                <Button
                  type="button"
                  variant="danger"
                  size="sm"
                  leftIcon={<Trash2 size={14} />}
                  loading={
                    deleteMutation.isPending &&
                    deleteMutation.variables === event.id
                  }
                  onClick={() =>
                    deleteMutation.mutate(event.id)
                  }
                >
                  Delete
                </Button>
              </div>
            </div>

            {event.description && (
              <p className="profile-muted">
                {event.description}
              </p>
            )}
          </article>
        ))}
      </div>
    </section>
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
    return <div className="profile-error">{error}</div>;
  }

  if (message) {
    return <div className="profile-success">{message}</div>;
  }

  return null;
}

function eventToForm(event: ProfileEvent): EventFormState {
  return {
    event_name: event.event_name,
    event_date: event.event_date.slice(0, 10),
    description: event.description ?? "",
    recurring: event.recurring,
  };
}

function eventPayload(
  form: EventFormState,
): Required<EventPayload> {
  return {
    event_name: form.event_name.trim(),
    event_date: form.event_date,
    description:
      form.description.trim().length > 0
        ? form.description.trim()
        : null,
    recurring: form.recurring,
  };
}

function makeInitials(identity: IdentityUser): string {
  const initials = identity.full_name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase() ?? "")
    .join("");

  return initials || identity.username.slice(0, 2).toUpperCase();
}

function formatDate(value: string): string {
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
  }).format(new Date(value));
}

function formatDateTime(value: string | null): string {
  if (!value) {
    return "unknown";
  }

  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

function errorMessage(error: unknown): string {
  if (isApiError(error)) {
    return error.message;
  }

  return "Profile request failed.";
}
