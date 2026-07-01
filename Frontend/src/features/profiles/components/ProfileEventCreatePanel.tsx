import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";

import { Button } from "../../../shared/ui/Button";
import {
  profileEventCreateSchema,
  type ProfileEventCreateFormValues,
} from "../schemas";
import { useCreateMyProfileEvent } from "../hooks";

type ProfileEventCreatePanelProps = {
  onCreated?: () => void;
  pendingLabel?: string;
  showHeading?: boolean;
  submitLabel?: string;
};

function toPayload(values: ProfileEventCreateFormValues) {
  return {
    event_name: values.event_name.trim(),
    event_date: values.event_date,
    description: values.description.trim() || undefined,
    recurring: values.recurring,
  };
}

export function ProfileEventCreatePanel({
  onCreated,
  pendingLabel = "Creating...",
  showHeading = true,
  submitLabel = "Create profile event",
}: ProfileEventCreatePanelProps = {}) {
  const createProfileEvent = useCreateMyProfileEvent();

  const {
    formState: { errors, isSubmitting },
    handleSubmit,
    register,
    reset,
  } = useForm<ProfileEventCreateFormValues>({
    resolver: zodResolver(profileEventCreateSchema),
    defaultValues: {
      event_name: "",
      event_date: "",
      description: "",
      recurring: true,
    },
  });

  async function onSubmit(values: ProfileEventCreateFormValues) {
    const result = await createProfileEvent.mutateAsync(toPayload(values));

    if (result.ok) {
      reset({
        event_name: "",
        event_date: "",
        description: "",
        recurring: true,
      });
      onCreated?.();
    }
  }

  const isDisabled = isSubmitting || createProfileEvent.isPending;

  return (
    <section className="account-settings-panel" aria-label="Create profile event">
      {showHeading ? (
        <div className="section-heading">
          <p className="eyebrow">Phase 2.11</p>
          <h2>Create Profile Event</h2>
          <p>
            Create one profile event using POST /profiles/me/events. After it
            is saved, it appears in the event list with its own edit and delete
            actions.
          </p>
        </div>
      ) : null}

      <form className="settings-form" onSubmit={handleSubmit(onSubmit)}>
        <label className="field-group">
          <span>Event name</span>
          <input
            {...register("event_name")}
            className="text-input"
            disabled={isDisabled}
            maxLength={80}
            placeholder="Birthday"
            type="text"
          />
          {errors.event_name ? (
            <small className="field-error">{errors.event_name.message}</small>
          ) : null}
        </label>

        <label className="field-group">
          <span>Event date</span>
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
          <span>Description</span>
          <textarea
            {...register("description")}
            className="text-input"
            disabled={isDisabled}
            maxLength={300}
            placeholder="Personal birthday event."
            rows={3}
          />
          {errors.description ? (
            <small className="field-error">{errors.description.message}</small>
          ) : null}
        </label>

        <label className="field-group">
          <span>Recurring event</span>
          <label className="checkbox-row">
            <input
              {...register("recurring")}
              disabled={isDisabled}
              type="checkbox"
            />
            <span>Repeat this event every year</span>
          </label>
          {errors.recurring ? (
            <small className="field-error">{errors.recurring.message}</small>
          ) : null}
        </label>

        {createProfileEvent.data && !createProfileEvent.data.ok ? (
          <div className="auth-error" role="alert">
            {createProfileEvent.data.message}
          </div>
        ) : null}

        {createProfileEvent.data?.ok ? (
          <div className="auth-success" role="status">
            <strong>Profile event created.</strong>
            <p>The read-only events section should refresh automatically.</p>
          </div>
        ) : null}

        {createProfileEvent.isError ? (
          <div className="auth-error" role="alert">
            Profile event request failed before the server returned a response.
          </div>
        ) : null}

        <div className="actions">
          <Button disabled={isDisabled} type="submit">
            {isDisabled ? pendingLabel : submitLabel}
          </Button>

          <Button
            disabled={isDisabled}
            onClick={() =>
              reset({
                event_name: "",
                event_date: "",
                description: "",
                recurring: true,
              })
            }
            type="button"
            variant="secondary"
          >
            Clear form
          </Button>
        </div>
      </form>
    </section>
  );
}
