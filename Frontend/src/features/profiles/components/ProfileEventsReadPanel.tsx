import { Button } from "../../../shared/ui/Button";
import { useMyProfileEvents } from "../hooks";
import type { ProfileEvent } from "../types";

function formatValue(value: string | number | boolean | null | undefined) {
  if (value === true) {
    return "Yes";
  }

  if (value === false) {
    return "No";
  }

  if (value === null || value === undefined || value === "") {
    return "Not added yet";
  }

  return String(value);
}

function getEventId(event: ProfileEvent) {
  return event.event_id ?? event.id ?? "unknown-event";
}

function formatEventSummary(event: ProfileEvent) {
  const name = formatValue(event.event_name);
  const date = formatValue(event.event_date);
  const recurring = event.recurring ? "Recurring" : "One time";

  return `${name} - ${date} - ${recurring}`;
}

type DetailRowProps = {
  label: string;
  value: string | number | boolean | null | undefined;
};

type ProfileEventsReadPanelProps = {
  onDeleteEvent?: (event: ProfileEvent) => void;
  onEditEvent?: (event: ProfileEvent) => void;
};

function DetailRow({ label, value }: DetailRowProps) {
  return (
    <div className="health-row">
      <strong>{label}</strong>
      <span>{formatValue(value)}</span>
    </div>
  );
}

export function ProfileEventsReadPanel({
  onDeleteEvent,
  onEditEvent,
}: ProfileEventsReadPanelProps) {
  const eventsQuery = useMyProfileEvents();
  const result = eventsQuery.data;
  const events = result?.ok ? result.data : undefined;

  return (
    <section className="account-settings-panel" aria-label="Profile events">
      <div className="section-heading">
        <p className="eyebrow">Phase 2.10</p>
        <h2>Profile Events</h2>
        <p>
          View your saved events and use the row actions to edit or delete a
          specific event.
        </p>
      </div>

      <div className="actions">
        <Button
          disabled={eventsQuery.isFetching}
          onClick={() => void eventsQuery.refetch()}
          type="button"
          variant="secondary"
        >
          {eventsQuery.isFetching ? "Refreshing events..." : "Refresh events"}
        </Button>
      </div>

      {eventsQuery.isPending ? (
        <div className="auth-success" role="status">
          <strong>Loading profile events...</strong>
          <p>Fetching profile events from Identity.</p>
        </div>
      ) : null}

      {!eventsQuery.isPending && result && !result.ok ? (
        <div className="auth-error" role="alert">
          {result.message}
        </div>
      ) : null}

      {!eventsQuery.isPending && eventsQuery.isError ? (
        <div className="auth-error" role="alert">
          Profile events request failed before the server returned a response.
        </div>
      ) : null}

      {!eventsQuery.isPending && result?.ok ? (
        <div className="health-panel">
          {events && events.length > 0 ? (
            <div className="profile-record-list">
              {events.map((event, index) => (
                <article
                  className="profile-record-item"
                  key={String(getEventId(event))}
                >
                  <div className="profile-record-header">
                    <div>
                      <h3>{`Event ${index + 1}`}</h3>
                      <span>{formatEventSummary(event)}</span>
                    </div>

                    {onEditEvent || onDeleteEvent ? (
                      <div className="profile-record-actions">
                        {onEditEvent ? (
                          <Button
                            onClick={() => onEditEvent(event)}
                            type="button"
                            variant="secondary"
                          >
                            Edit
                          </Button>
                        ) : null}

                        {onDeleteEvent ? (
                          <Button
                            onClick={() => onDeleteEvent(event)}
                            type="button"
                            variant="danger"
                          >
                            Delete
                          </Button>
                        ) : null}
                      </div>
                    ) : null}
                  </div>

                  <div className="profile-record-grid">
                    <DetailRow label="Event ID" value={getEventId(event)} />
                    <DetailRow label="Event name" value={event.event_name} />
                    <DetailRow label="Event date" value={event.event_date} />
                    <DetailRow label="Description" value={event.description} />
                    <DetailRow label="Recurring" value={event.recurring} />
                  </div>
                </article>
              ))}
            </div>
          ) : (
            <div className="health-row">
              <strong>Events</strong>
              <span>No events added yet</span>
            </div>
          )}
        </div>
      ) : null}
    </section>
  );
}
