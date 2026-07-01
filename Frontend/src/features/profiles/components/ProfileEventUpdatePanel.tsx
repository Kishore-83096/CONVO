import { zodResolver } from "@hookform/resolvers/zod";
import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";

import { Button } from "../../../shared/ui/Button";
import {
  profileEventUpdateSchema,
  type ProfileEventUpdateFormValues,
} from "../schemas";
import { useUpdateMyProfileEvent } from "../hooks";
import type { ProfileEvent } from "../types";

type ProfileEventUpdatePanelProps = {
  clearLabel?: string;
  event?: ProfileEvent | null;
  pendingLabel?: string;
  onUpdated?: () => void;
  showHeading?: boolean;
  submitLabel?: string;
};

function getEventId(event: ProfileEvent | null | undefined) {
  return event?.event_id ?? event?.id ?? "";
}

function toPayload(values: ProfileEventUpdateFormValues) {
  return {
    event_name: values.event_name.trim() || undefined,
    event_date: values.event_date.trim() || undefined,
    description: values.description.trim() || undefined,
    recurring: values.update_recurring ? values.recurring : undefined,
  };
}

export function ProfileEventUpdatePanel({
  clearLabel = "Clear form",
  event,
  pendingLabel = "Updating...",
  onUpdated,
  showHeading = true,
  submitLabel = "Update profile event",
}: ProfileEventUpdatePanelProps) {
  const [shouldUpdateRecurring, setShouldUpdateRecurring] = useState(false);
  const updateProfileEvent = useUpdateMyProfileEvent();
  const selectedEventId = String(getEventId(event));

  const {
    formState: { errors, isSubmitting },
    handleSubmit,
    register,
    reset,
    setValue,
  } = useForm<ProfileEventUpdateFormValues>({
    resolver: zodResolver(profileEventUpdateSchema),
    defaultValues: {
      event_id: "",
      event_name: "",
      event_date: "",
      description: "",
      update_recurring: false,
      recurring: true,
    },
  });

  useEffect(() => {
    if (!event) {
      return;
    }

    reset({
      event_id: selectedEventId,
      event_name: event.event_name ?? "",
      event_date: event.event_date ?? "",
      description: event.description ?? "",
      update_recurring: false,
      recurring: event.recurring ?? true,
    });
    window.queueMicrotask(() => {
    setShouldUpdateRecurring(false);
  });
  }, [event, reset, selectedEventId]);

  async function onSubmit(values: ProfileEventUpdateFormValues) {
    const eventId = selectedEventId || values.event_id.trim();
    const result = await updateProfileEvent.mutateAsync({
      eventId,
      data: toPayload(values),
    });

    if (result.ok) {
      if (onUpdated) {
        onUpdated();
      } else {
        reset({
          event_id: eventId,
          event_name: "",
          event_date: "",
          description: "",
          update_recurring: false,
          recurring: true,
        });
      }

      setShouldUpdateRecurring(false);
    }
  }

  function clearForm() {
    if (event) {
      reset({
        event_id: selectedEventId,
        event_name: event.event_name ?? "",
        event_date: event.event_date ?? "",
        description: event.description ?? "",
        update_recurring: false,
        recurring: event.recurring ?? true,
      });
      setShouldUpdateRecurring(false);
      return;
    }

    reset({
      event_id: "",
      event_name: "",
      event_date: "",
      description: "",
      update_recurring: false,
      recurring: true,
    });

    setShouldUpdateRecurring(false);
  }

  const isDisabled = isSubmitting || updateProfileEvent.isPending;

  return (
    <section className="account-settings-panel" aria-label="Update profile event">
      {showHeading ? (
        <div className="section-heading">
          <p className="eyebrow">Phase 2.13</p>
          <h2>Edit Profile Event</h2>
          <p>
            Update the selected event using PATCH
            /profiles/me/events/&#123;event_id&#125;.
          </p>
        </div>
      ) : null}

      <form className="settings-form" onSubmit={handleSubmit(onSubmit)}>
        {selectedEventId ? (
          <div className="profile-linked-record">
            <input {...register("event_id")} type="hidden" />
            <strong>Selected event</strong>
            <span>{event?.event_name || selectedEventId}</span>
          </div>
        ) : (
          <label className="field-group">
            <span>Event ID</span>
            <input
              {...register("event_id")}
              className="text-input"
              disabled={isDisabled}
              placeholder="Paste event ID"
              type="text"
            />
            {errors.event_id ? (
              <small className="field-error">{errors.event_id.message}</small>
            ) : null}
          </label>
        )}

        <label className="field-group">
          <span>New event name</span>
          <input
            {...register("event_name")}
            className="text-input"
            disabled={isDisabled}
            maxLength={80}
            placeholder="New event name"
            type="text"
          />
          {errors.event_name ? (
            <small className="field-error">{errors.event_name.message}</small>
          ) : null}
        </label>

        <label className="field-group">
          <span>New event date</span>
          <input
            {...register("event_date")}
            className="text-input"
            disabled={isDisabled}
            type="date"
          />
          {errors.event_date ? (
            <small className="field-error">{errors.event_date.message}</small>
          ) : null}
        </label>

        <label className="field-group">
          <span>New description</span>
          <textarea
            {...register("description")}
            className="text-input"
            disabled={isDisabled}
            maxLength={300}
            placeholder="Updated event description"
            rows={3}
          />
          {errors.description ? (
            <small className="field-error">{errors.description.message}</small>
          ) : null}
        </label>

        <label className="field-group">
          <span>Recurring update</span>
          <label className="checkbox-row">
            <input
              {...register("update_recurring")}
              disabled={isDisabled}
              onChange={(event) => {
                const checked = event.target.checked;

                setShouldUpdateRecurring(checked);
                setValue("update_recurring", checked);

                if (!checked) {
                  setValue("recurring", true);
                }
              }}
              type="checkbox"
            />
            <span>Update recurring setting</span>
          </label>
        </label>

        <label className="field-group">
          <span>Recurring value</span>
          <label className="checkbox-row">
            <input
              {...register("recurring")}
              disabled={isDisabled || !shouldUpdateRecurring}
              type="checkbox"
            />
            <span>Repeat this event every year</span>
          </label>
          {errors.recurring ? (
            <small className="field-error">{errors.recurring.message}</small>
          ) : null}
        </label>

        {updateProfileEvent.data && !updateProfileEvent.data.ok ? (
          <div className="auth-error" role="alert">
            {updateProfileEvent.data.message}
          </div>
        ) : null}

        {updateProfileEvent.data?.ok ? (
          <div className="auth-success" role="status">
            <strong>Profile event updated.</strong>
            <p>The events list should refresh automatically.</p>
          </div>
        ) : null}

        {updateProfileEvent.isError ? (
          <div className="auth-error" role="alert">
            Profile event update failed before the server returned a response.
          </div>
        ) : null}

        <div className="actions">
          <Button disabled={isDisabled} type="submit">
            {isDisabled ? pendingLabel : submitLabel}
          </Button>

          <Button
            disabled={isDisabled}
            onClick={clearForm}
            type="button"
          variant="secondary"
        >
            {clearLabel}
          </Button>
        </div>
      </form>
    </section>
  );
}
