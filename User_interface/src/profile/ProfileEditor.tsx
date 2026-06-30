import { useEffect, useState } from "react";
import { Save, Trash2 } from "lucide-react";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import Button from "@/ui/Button";
import { isApiError } from "@/api/api-errors";

import {
  profileApi,
  type AddressPayload,
  type BasicProfile,
  type BasicProfilePayload,
  type ProfileAddress,
} from "./profile-api";

interface ProfileEditorProps {
  basic: BasicProfile | null;
  address: ProfileAddress | null;
}

interface BasicFormState {
  bio: string;
  date_of_birth: string;
  gender: string;
  occupation: string;
  website: string;
}

interface AddressFormState {
  address_line_1: string;
  address_line_2: string;
  city: string;
  state: string;
  postal_code: string;
  country: string;
}

const emptyBasicForm: BasicFormState = {
  bio: "",
  date_of_birth: "",
  gender: "",
  occupation: "",
  website: "",
};

const emptyAddressForm: AddressFormState = {
  address_line_1: "",
  address_line_2: "",
  city: "",
  state: "",
  postal_code: "",
  country: "",
};

export function ProfileEditor({
  basic,
  address,
}: ProfileEditorProps) {
  return (
    <>
      <BasicProfileEditor basic={basic} />
      <AddressEditor address={address} />
    </>
  );
}

function BasicProfileEditor({
  basic,
}: {
  basic: BasicProfile | null;
}) {
  const queryClient = useQueryClient();
  const [form, setForm] = useState<BasicFormState>(
    basicToForm(basic),
  );
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setForm(basicToForm(basic));
  }, [basic]);

  const invalidateProfile = async () => {
    await queryClient.invalidateQueries({
      queryKey: ["profile", "complete"],
    });
  };

  const saveMutation = useMutation({
    mutationFn: (payload: BasicProfilePayload) =>
      basic
        ? profileApi.patchBasic(payload)
        : profileApi.createBasic(payload),
    onSuccess: async (response) => {
      setMessage(response.message);
      setError(null);
      await invalidateProfile();
    },
    onError: (mutationError) => {
      setMessage(null);
      setError(errorMessage(mutationError));
    },
  });

  const deleteMutation = useMutation({
    mutationFn: () => profileApi.deleteBasic(),
    onSuccess: async (response) => {
      setForm(emptyBasicForm);
      setMessage(response.message);
      setError(null);
      await invalidateProfile();
    },
    onError: (mutationError) => {
      setMessage(null);
      setError(errorMessage(mutationError));
    },
  });

  function updateField(
    field: keyof BasicFormState,
    value: string,
  ) {
    setForm((current) => ({
      ...current,
      [field]: value,
    }));
  }

  function handleSubmit() {
    const payload = compactPayload({
      bio: nullable(form.bio),
      date_of_birth: nullable(form.date_of_birth),
      gender: nullable(form.gender),
      occupation: nullable(form.occupation),
      website: nullable(form.website),
    });

    if (Object.keys(payload).length === 0) {
      setMessage(null);
      setError("Add at least one basic profile field.");
      return;
    }

    saveMutation.mutate(payload);
  }

  return (
    <section className="profile-panel">
      <div className="profile-panel__header">
        <div>
          <h2>Basic Profile</h2>
          <p>Bio, date of birth, gender, occupation, and website.</p>
        </div>
      </div>

      <Feedback message={message} error={error} />

      <div className="profile-form">
        <label className="profile-field">
          <span>Bio</span>
          <textarea
            maxLength={500}
            value={form.bio}
            onChange={(event) =>
              updateField("bio", event.target.value)
            }
          />
          <small>{form.bio.length}/500</small>
        </label>

        <div className="profile-form__row">
          <label className="profile-field">
            <span>Date of birth</span>
            <input
              type="date"
              value={form.date_of_birth}
              onChange={(event) =>
                updateField(
                  "date_of_birth",
                  event.target.value,
                )
              }
            />
          </label>

          <label className="profile-field">
            <span>Gender</span>
            <input
              maxLength={50}
              value={form.gender}
              onChange={(event) =>
                updateField("gender", event.target.value)
              }
            />
          </label>
        </div>

        <div className="profile-form__row">
          <label className="profile-field">
            <span>Occupation</span>
            <input
              maxLength={100}
              value={form.occupation}
              onChange={(event) =>
                updateField("occupation", event.target.value)
              }
            />
          </label>

          <label className="profile-field">
            <span>Website</span>
            <input
              type="url"
              value={form.website}
              onChange={(event) =>
                updateField("website", event.target.value)
              }
            />
          </label>
        </div>

        <div className="profile-actions">
          {basic && (
            <Button
              type="button"
              variant="danger"
              leftIcon={<Trash2 size={16} />}
              loading={deleteMutation.isPending}
              onClick={() => deleteMutation.mutate()}
            >
              Delete Basic Data
            </Button>
          )}

          <Button
            type="button"
            leftIcon={<Save size={16} />}
            loading={saveMutation.isPending}
            onClick={handleSubmit}
          >
            {basic ? "Save Basic Data" : "Create Basic Data"}
          </Button>
        </div>
      </div>
    </section>
  );
}

function AddressEditor({
  address,
}: {
  address: ProfileAddress | null;
}) {
  const queryClient = useQueryClient();
  const [form, setForm] = useState<AddressFormState>(
    addressToForm(address),
  );
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setForm(addressToForm(address));
  }, [address]);

  const invalidateProfile = async () => {
    await queryClient.invalidateQueries({
      queryKey: ["profile", "complete"],
    });
  };

  const saveMutation = useMutation({
    mutationFn: (payload: AddressPayload) =>
      address
        ? profileApi.patchAddress(payload)
        : profileApi.createAddress(payload),
    onSuccess: async (response) => {
      setMessage(response.message);
      setError(null);
      await invalidateProfile();
    },
    onError: (mutationError) => {
      setMessage(null);
      setError(errorMessage(mutationError));
    },
  });

  const deleteMutation = useMutation({
    mutationFn: () => profileApi.deleteAddress(),
    onSuccess: async (response) => {
      setForm(emptyAddressForm);
      setMessage(response.message);
      setError(null);
      await invalidateProfile();
    },
    onError: (mutationError) => {
      setMessage(null);
      setError(errorMessage(mutationError));
    },
  });

  function updateField(
    field: keyof AddressFormState,
    value: string,
  ) {
    setForm((current) => ({
      ...current,
      [field]: value,
    }));
  }

  function handleSubmit() {
    const payload = compactPayload({
      address_line_1: nullable(form.address_line_1),
      address_line_2: nullable(form.address_line_2),
      city: nullable(form.city),
      state: nullable(form.state),
      postal_code: nullable(form.postal_code),
      country: nullable(form.country),
    });

    if (!address) {
      const missingRequired =
        !payload.address_line_1 ||
        !payload.city ||
        !payload.country;

      if (missingRequired) {
        setMessage(null);
        setError(
          "Address line 1, city, and country are required.",
        );
        return;
      }
    }

    if (Object.keys(payload).length === 0) {
      setMessage(null);
      setError("Add at least one address field.");
      return;
    }

    saveMutation.mutate(payload);
  }

  return (
    <section className="profile-panel">
      <div className="profile-panel__header">
        <div>
          <h2>Address</h2>
          <p>Manage your profile address details.</p>
        </div>
      </div>

      <Feedback message={message} error={error} />

      <div className="profile-form">
        <div className="profile-form__row">
          <label className="profile-field">
            <span>Address line 1</span>
            <input
              maxLength={150}
              required={!address}
              value={form.address_line_1}
              onChange={(event) =>
                updateField(
                  "address_line_1",
                  event.target.value,
                )
              }
            />
          </label>

          <label className="profile-field">
            <span>Address line 2</span>
            <input
              maxLength={150}
              value={form.address_line_2}
              onChange={(event) =>
                updateField(
                  "address_line_2",
                  event.target.value,
                )
              }
            />
          </label>
        </div>

        <div className="profile-form__row">
          <label className="profile-field">
            <span>City</span>
            <input
              maxLength={100}
              required={!address}
              value={form.city}
              onChange={(event) =>
                updateField("city", event.target.value)
              }
            />
          </label>

          <label className="profile-field">
            <span>State</span>
            <input
              maxLength={100}
              value={form.state}
              onChange={(event) =>
                updateField("state", event.target.value)
              }
            />
          </label>
        </div>

        <div className="profile-form__row">
          <label className="profile-field">
            <span>Postal code</span>
            <input
              maxLength={20}
              value={form.postal_code}
              onChange={(event) =>
                updateField(
                  "postal_code",
                  event.target.value,
                )
              }
            />
          </label>

          <label className="profile-field">
            <span>Country</span>
            <input
              maxLength={100}
              required={!address}
              value={form.country}
              onChange={(event) =>
                updateField("country", event.target.value)
              }
            />
          </label>
        </div>

        <div className="profile-actions">
          {address && (
            <Button
              type="button"
              variant="danger"
              leftIcon={<Trash2 size={16} />}
              loading={deleteMutation.isPending}
              onClick={() => deleteMutation.mutate()}
            >
              Delete Address
            </Button>
          )}

          <Button
            type="button"
            leftIcon={<Save size={16} />}
            loading={saveMutation.isPending}
            onClick={handleSubmit}
          >
            {address ? "Save Address" : "Create Address"}
          </Button>
        </div>
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

function basicToForm(
  basic: BasicProfile | null,
): BasicFormState {
  if (!basic) {
    return emptyBasicForm;
  }

  return {
    bio: basic.bio ?? "",
    date_of_birth: dateOnly(basic.date_of_birth),
    gender: basic.gender ?? "",
    occupation: basic.occupation ?? "",
    website: basic.website ?? "",
  };
}

function addressToForm(
  address: ProfileAddress | null,
): AddressFormState {
  if (!address) {
    return emptyAddressForm;
  }

  return {
    address_line_1: address.address_line_1 ?? "",
    address_line_2: address.address_line_2 ?? "",
    city: address.city ?? "",
    state: address.state ?? "",
    postal_code: address.postal_code ?? "",
    country: address.country ?? "",
  };
}

function compactPayload<T extends Record<string, unknown>>(
  payload: T,
): Partial<T> {
  return Object.fromEntries(
    Object.entries(payload).filter(([, value]) => {
      if (value === undefined) {
        return false;
      }

      if (typeof value === "string") {
        return value.trim().length > 0;
      }

      return value !== null;
    }),
  ) as Partial<T>;
}

function nullable(value: string): string | null {
  const trimmed = value.trim();
  return trimmed.length > 0 ? trimmed : null;
}

function dateOnly(value: string | null): string {
  return value ? value.slice(0, 10) : "";
}

function errorMessage(error: unknown): string {
  if (isApiError(error)) {
    return error.message;
  }

  return "Profile changes could not be saved.";
}
