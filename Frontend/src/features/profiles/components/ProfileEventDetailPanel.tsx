import { useState } from "react";

import { Button } from "../../../shared/ui/Button";
import { useMyProfileEvent } from "../hooks";

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

type DetailRowProps = {
  label: string;
  value: string | number | boolean | null | undefined;
};

function DetailRow({ label, value }: DetailRowProps) {
  return (
    <div className="health-row">
      <strong>{label}</strong>
      <span>{formatValue(value)}</span>
    </div>
  );
}

export function ProfileEventDetailPanel() {
  const [eventIdInput, setEventIdInput] = useState("");
  const [selectedEventId, setSelectedEventId] = useState("");

  const eventQuery = useMyProfileEvent(selectedEventId);
  const result = eventQuery.data;
  const event = result?.ok ? result.data : undefined;

  function handleFetchEvent() {
    setSelectedEventId(eventIdInput.trim());
  }

  return (
    <section className="account-settings-panel" aria-label="Profile event detail">
      <div className="section-heading">
        <p className="eyebrow">Phase 2.12</p>
        <h2>Read One Profile Event</h2>
        <p>
          Copy an Event ID from the Profile Events list above, paste it here,
          and fetch that one event using GET /profiles/me/events/&#123;event_id&#125;.
        </p>
      </div>

      <label className="field-group">
        <span>Event ID</span>
        <input
          className="text-input"
          disabled={eventQuery.isFetching}
          onChange={(event) => setEventIdInput(event.target.value)}
          placeholder="Paste event ID"
          type="text"
          value={eventIdInput}
        />
      </label>

      <div className="actions">
        <Button
          disabled={eventQuery.isFetching || eventIdInput.trim().length === 0}
          onClick={handleFetchEvent}
          type="button"
        >
          {eventQuery.isFetching ? "Fetching event..." : "Fetch event"}
        </Button>

        <Button
          disabled={eventQuery.isFetching}
          onClick={() => {
            setEventIdInput("");
            setSelectedEventId("");
          }}
          type="button"
          variant="secondary"
        >
          Clear
        </Button>
      </div>

      {eventQuery.isPending && selectedEventId ? (
        <div className="auth-success" role="status">
          <strong>Loading event...</strong>
          <p>Fetching one profile event from Identity.</p>
        </div>
      ) : null}

      {!eventQuery.isPending && result && !result.ok ? (
        <div className="auth-error" role="alert">
          {result.message}
        </div>
      ) : null}

      {!eventQuery.isPending && eventQuery.isError ? (
        <div className="auth-error" role="alert">
          Profile event detail request failed before the server returned a
          response.
        </div>
      ) : null}

      {!eventQuery.isPending && result?.ok && event ? (
        <div className="health-panel">
          <DetailRow label="Event ID" value={event.event_id ?? event.id} />
          <DetailRow label="Event name" value={event.event_name} />
          <DetailRow label="Event date" value={event.event_date} />
          <DetailRow label="Description" value={event.description} />
          <DetailRow label="Recurring" value={event.recurring} />
        </div>
      ) : null}
    </section>
  );
}