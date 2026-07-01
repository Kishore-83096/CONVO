import { useState } from "react";

import { WarningModal } from "../../../shared/ui/WarningModal";
import { useDeleteMyProfileEvent } from "../hooks";
import type { ProfileEvent } from "../types";

type ProfileEventDeletePanelProps = {
  event?: ProfileEvent | null;
  onCancel?: () => void;
  onDeleted?: () => void;
};

function getEventId(event: ProfileEvent | null | undefined) {
  return event?.event_id ?? event?.id ?? "";
}

export function ProfileEventDeletePanel({
  event,
  onCancel,
  onDeleted,
}: ProfileEventDeletePanelProps) {
  const [eventId, setEventId] = useState("");
  const [isWarningOpen, setIsWarningOpen] = useState(true);
  const deleteProfileEvent = useDeleteMyProfileEvent();

  const selectedEventId = String(getEventId(event));
  const trimmedEventId = selectedEventId || eventId.trim();
  const isDisabled = deleteProfileEvent.isPending;

  function closeWarning() {
    setIsWarningOpen(false);
    onCancel?.();
  }

  async function handleDeleteProfileEvent() {
    if (!trimmedEventId) {
      return;
    }

    const result = await deleteProfileEvent.mutateAsync(trimmedEventId);

    if (result.ok) {
      setEventId("");
      setIsWarningOpen(false);
      onDeleted?.();
    }
  }

  return (
    <WarningModal
      confirmLabel="Delete event"
      description={`This removes ${
        event?.event_name ? `"${event.event_name}"` : "the selected event"
      } from your profile events.`}
      isBusy={isDisabled}
      isOpen={Boolean(trimmedEventId) && isWarningOpen}
      onClose={closeWarning}
      onConfirm={handleDeleteProfileEvent}
      title="Delete profile event?"
    >
      {deleteProfileEvent.data && !deleteProfileEvent.data.ok ? (
        <div className="auth-error" role="alert">
          {deleteProfileEvent.data.message}
        </div>
      ) : null}

      {deleteProfileEvent.data?.ok ? (
        <div className="auth-success" role="status">
          <strong>Profile event deleted.</strong>
          <p>The events list should refresh automatically.</p>
        </div>
      ) : null}

      {deleteProfileEvent.isError ? (
        <div className="auth-error" role="alert">
          Profile event delete failed before the server returned a response.
        </div>
      ) : null}
    </WarningModal>
  );
}
