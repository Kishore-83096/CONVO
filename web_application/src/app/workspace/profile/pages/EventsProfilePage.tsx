import { useState, type FormEvent } from "react"

import {
  createEvent,
  deleteEvent,
  updateEvent,
} from "@/app/workspace/profile/profile.api"
import type {
  CompleteProfile,
  EventCreateInput,
  ProfileEvent,
} from "@/app/workspace/profile/profile.types"

interface EventsProfilePageProps {
  accessToken: string
  profile: CompleteProfile
  onUpdated: () => void
}

function fieldText(formData: FormData, name: string) {
  return String(formData.get(name) ?? "").trim()
}

function optionalFieldText(formData: FormData, name: string) {
  const text = fieldText(formData, name)
  return text.length ? text : null
}

function EventsProfilePage({
  accessToken,
  profile,
  onUpdated,
}: EventsProfilePageProps) {
  const [editingEvent, setEditingEvent] = useState<ProfileEvent | null>(null)
  const [message, setMessage] = useState("")
  const [error, setError] = useState("")
  const [isSubmitting, setIsSubmitting] = useState(false)
  const events = profile.events
  const isEventLimitReached = events.length >= 5 && !editingEvent

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const formData = new FormData(event.currentTarget)
    const request: EventCreateInput = {
      event_name: fieldText(formData, "event_name"),
      event_date: fieldText(formData, "event_date"),
      description: optionalFieldText(formData, "description"),
      recurring: formData.get("recurring") === "on",
    }

    setIsSubmitting(true)
    setMessage("")
    setError("")

    try {
      if (editingEvent) {
        await updateEvent(editingEvent.id, request, accessToken)
      } else {
        await createEvent(request, accessToken)
      }

      setMessage(editingEvent ? "Event updated." : "Event created.")
      setEditingEvent(null)
      onUpdated()
      event.currentTarget.reset()
    } catch (submitError) {
      setError(
        submitError instanceof Error
          ? submitError.message
          : "Unable to save event.",
      )
    } finally {
      setIsSubmitting(false)
    }
  }

  const handleDelete = async (eventId: number) => {
    setIsSubmitting(true)
    setMessage("")
    setError("")

    try {
      await deleteEvent(eventId, accessToken)
      setMessage("Event deleted.")
      if (editingEvent?.id === eventId) {
        setEditingEvent(null)
      }
      onUpdated()
    } catch (deleteError) {
      setError(
        deleteError instanceof Error
          ? deleteError.message
          : "Unable to delete event.",
      )
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <section className="workspace-panel active">
      <div className="profile-list">
        {events.length === 0 ? (
          <p className="contacts-state">No events saved yet.</p>
        ) : (
          events.map((profileEvent) => (
            <article className="profile-row" key={profileEvent.id}>
              <div>
                <strong>{profileEvent.event_name}</strong>
                <span>
                  {profileEvent.event_date}
                  {profileEvent.recurring ? " · recurring" : ""}
                </span>
                {profileEvent.description ? (
                  <p>{profileEvent.description}</p>
                ) : null}
              </div>
              <div className="profile-row-actions">
                <button
                  className="secondary-action-button"
                  type="button"
                  onClick={() => setEditingEvent(profileEvent)}
                >
                  Edit
                </button>
                <button
                  className="secondary-action-button"
                  type="button"
                  disabled={isSubmitting}
                  onClick={() => void handleDelete(profileEvent.id)}
                >
                  Delete
                </button>
              </div>
            </article>
          ))
        )}
      </div>

      <form className="flat-form" onSubmit={handleSubmit}>
        <div className="form-field">
          <label htmlFor="event_name">Event name</label>
          <input
            id="event_name"
            name="event_name"
            maxLength={80}
            defaultValue={editingEvent?.event_name ?? ""}
            required
          />
        </div>
        <div className="form-field">
          <label htmlFor="event_date">Event date</label>
          <input
            id="event_date"
            name="event_date"
            type="date"
            defaultValue={editingEvent?.event_date ?? ""}
            required
          />
        </div>
        <div className="form-field form-field-wide">
          <label htmlFor="description">Description</label>
          <textarea
            id="description"
            name="description"
            maxLength={300}
            defaultValue={editingEvent?.description ?? ""}
          />
        </div>
        <label className="profile-check form-field-wide">
          <input
            key={editingEvent?.id ?? "new-event"}
            name="recurring"
            type="checkbox"
            defaultChecked={editingEvent?.recurring ?? true}
          />
          <span>Recurring event</span>
        </label>
        <div className="form-actions form-field-wide">
          <button
            className="secondary-action-button"
            type="button"
            onClick={() => setEditingEvent(null)}
          >
            New Event
          </button>
          <button
            className="primary-action-button"
            type="submit"
            disabled={isSubmitting || isEventLimitReached}
          >
            {editingEvent ? "Update Event" : "Create Event"}
          </button>
        </div>
      </form>
      {isEventLimitReached ? (
        <p className="profile-message">You can save up to five events.</p>
      ) : null}
      {message ? <p className="profile-message">{message}</p> : null}
      {error ? (
        <p className="profile-error" role="alert">
          {error}
        </p>
      ) : null}
    </section>
  )
}

export default EventsProfilePage
