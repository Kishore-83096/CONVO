import {
  createBrowserRouter,
  Navigate,
} from "react-router-dom";

import { AppShell, PublicLayout } from "@/components/layout";
import { RequireAuth } from "@/auth/RequireAuth";
import { RequireUsername } from "@/auth/RequireUsername";
import { useAuth } from "@/auth/use-auth";
import {
  userHomePath,
  userWorkspacePath,
} from "@/auth/auth-routes";

import { LandingPage } from "@/pages/LandingPage";
import { LoginPage } from "@/pages/LoginPage";
import { RegisterPage } from "@/pages/RegisterPage";
import { RedirectIfAuthenticated } from "@/auth/RedirectIfAuthenticated";
import { MessengerPage } from "@/pages/MessengerPage";
import { ContactsPage } from "@/pages/ContactsPage";
import { ProfilePage } from "@/pages/ProfilePage";
import { SettingsPage } from "@/pages/SettingsPage";

function AuthenticatedRedirect({
  section,
}: {
  section?: "contacts" | "profile" | "settings";
}) {
  const { session } = useAuth();
  const to = section
    ? userWorkspacePath(session, section)
    : userHomePath(session);

  return <Navigate to={to} replace />;
}

export const router = createBrowserRouter([
  // ---------------------------------------
  // Public Routes
  // ---------------------------------------
  {
  element: <PublicLayout />,
  children: [
    {
      element: <RedirectIfAuthenticated />,
      children: [
        {
          path: "/",
          element: <LandingPage />,
        },
        {
          path: "/login",
          element: <LoginPage />,
        },
        {
          path: "/register",
          element: <RegisterPage />,
        },
      ],
    },
  ],
},

  // ---------------------------------------
  // Protected Routes
  // ---------------------------------------
  {
    element: <RequireAuth />,
    children: [
      {
        path: "/app",
        element: <AuthenticatedRedirect />,
      },
      {
        path: "/contacts",
        element: <AuthenticatedRedirect section="contacts" />,
      },
      {
        path: "/profile",
        element: <AuthenticatedRedirect section="profile" />,
      },
      {
        path: "/settings",
        element: <AuthenticatedRedirect section="settings" />,
      },
      {
        element: <RequireUsername />,
        children: [
          {
            element: <AppShell />,
            children: [
              {
                path: "/:username",
                element: <MessengerPage />,
              },
              {
                path: "/:username/contacts",
                element: <ContactsPage />,
              },
              {
                path: "/:username/profile",
                element: <ProfilePage />,
              },
              {
                path: "/:username/settings",
                element: <SettingsPage />,
              },
            ],
          },
        ],
      },
    ],
  },
]);

export default router;
