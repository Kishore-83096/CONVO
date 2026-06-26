import { Link } from "react-router"

import SeoMeta from "@/app/seo/SeoMeta"
import { absoluteUrl } from "@/app/seo/seo-url"
import BrandThemeIcon from "@/components/BrandThemeIcon"

import "./PublicPages.css"

type PublicPageKey = "home" | "features" | "security" | "privacy" | "about" | "contact"

interface PublicPageContent {
  description: string
  h1: string
  path: string
  sections: {
    body: string
    title: string
  }[]
  title: string
}

const homepageDescription =
  "Myna is a privacy-focused real-time messaging application for private conversations, instant communication, contact management, and secure message delivery."

const pages: Record<PublicPageKey, PublicPageContent> = {
  home: {
    path: "/",
    title: "Myna – Private Real-Time Messaging Application",
    description: homepageDescription,
    h1: "Myna – Private Real-Time Messaging",
    sections: [
      {
        title: "What is Myna?",
        body: "Myna is a web-based communication platform that helps users manage contacts and exchange messages through a simple, privacy-focused real-time messaging experience.",
      },
      {
        title: "Real-time messaging",
        body: "Myna provides a focused chat workspace for quick conversations and message workflows in a clean browser-based interface.",
      },
      {
        title: "Private conversations",
        body: "Authenticated areas keep personal messaging, profile, account, and contact screens separate from public website pages.",
      },
      {
        title: "Contact management",
        body: "Users can find contacts, save people they communicate with, rename saved contacts, and keep conversations organized.",
      },
      {
        title: "Message delivery",
        body: "The application is designed around instant communication flows and clear message screens for everyday conversations.",
      },
      {
        title: "Privacy and security",
        body: "Myna keeps private application routes out of the public sitemap and uses authenticated sessions for private screens.",
      },
      {
        title: "Simple communication experience",
        body: "The interface is designed to make account creation, sign in, profile management, and messaging feel direct and easy to navigate.",
      },
      {
        title: "Sign in",
        body: "Existing users can sign in from the public navigation to access their private Myna workspace.",
      },
      {
        title: "Create an account",
        body: "New users can create an account and start setting up their profile and contacts.",
      },
    ],
  },
  features: {
    path: "/features",
    title: "Myna Features - Real-Time Messaging and Contact Management",
    description:
      "Explore Myna features for real-time messaging, contact management, profiles, and a simple communication workspace.",
    h1: "Myna features for messaging and contacts",
    sections: [
      {
        title: "Messaging workspace",
        body: "Myna gives users a dedicated space for conversations, message composition, and contact-based communication.",
      },
      {
        title: "Saved contacts",
        body: "Contact tools help users search, save, rename, view, and remove contacts from their personal workspace.",
      },
      {
        title: "Profile tools",
        body: "Users can manage profile details, profile pictures, address information, and important events after signing in.",
      },
      {
        title: "Simple account flow",
        body: "Sign-in and registration screens are available from the public navigation, while private workspaces remain authenticated.",
      },
    ],
  },
  security: {
    path: "/security",
    title: "Security and Privacy - Myna",
    description:
      "Learn how Myna separates public information from authenticated messaging, profile, account, and contact pages.",
    h1: "Security and privacy in Myna",
    sections: [
      {
        title: "Authenticated private pages",
        body: "Messaging, profile, account, and contact screens are treated as private application areas and are excluded from the public sitemap.",
      },
      {
        title: "Session-based access",
        body: "Myna uses authenticated sessions to protect private app screens. Search engine metadata is not used as a replacement for authorization.",
      },
      {
        title: "Careful public content",
        body: "Public SEO pages describe the product without exposing private user information, contact data, or chat content.",
      },
    ],
  },
  privacy: {
    path: "/privacy",
    title: "Privacy Policy - Myna",
    description:
      "Read Myna privacy information about public pages, account data, contacts, and private messaging areas.",
    h1: "Myna privacy policy",
    sections: [
      {
        title: "Public website pages",
        body: "Myna public pages contain product information and links for visitors. They do not publish authenticated chat content.",
      },
      {
        title: "Account and contact data",
        body: "Account, contact, and profile information is handled inside authenticated application areas and should be accessed only by authorized users.",
      },
      {
        title: "Operational note",
        body: "This page provides general privacy information for the application. A final production privacy policy should be reviewed for your actual hosting, analytics, and data handling practices.",
      },
    ],
  },
  about: {
    path: "/about",
    title: "About Myna - Private Real-Time Messaging",
    description:
      "About Myna, a web-based real-time messaging application for private conversations and contact management.",
    h1: "About Myna",
    sections: [
      {
        title: "What Myna is",
        body: "Myna is a browser-based messaging application focused on private real-time communication, clean navigation, and everyday contact workflows.",
      },
      {
        title: "Why the name Myna",
        body: "The name was chosen as a nod to the myna bird, which is known for vocal communication and mimicking sounds.",
      },
      {
        title: "Development purpose",
        body: "The application brings account identity, profiles, contacts, and chat screens into one consistent user experience for learning and production-oriented development.",
      },
    ],
  },
  contact: {
    path: "/contact",
    title: "Contact Myna",
    description:
      "Contact Myna for questions about the messaging application, accounts, privacy, or support.",
    h1: "Contact Myna",
    sections: [
      {
        title: "Support",
        body: "For production, add the official Myna support email, business address, or contact form endpoint here.",
      },
      {
        title: "Account access",
        body: "Existing users should sign in to access private account, profile, contact, and messaging tools.",
      },
    ],
  },
}

const navLinks = [
  { href: "/", label: "Home" },
  { href: "/features", label: "Features" },
  { href: "/security", label: "Security" },
  { href: "/privacy", label: "Privacy" },
  { href: "/about", label: "About" },
  { href: "/contact", label: "Contact" },
]

function PublicNav() {
  return (
    <header className="public-header">
      <nav className="public-nav" aria-label="Myna public navigation">
        <Link className="public-brand" to="/">
          <BrandThemeIcon width="42" height="42" />
          <span>Myna</span>
        </Link>

        <div className="public-nav-links">
          {navLinks.map((link) => (
            <Link key={link.href} to={link.href}>
              {link.label}
            </Link>
          ))}
        </div>

        <div className="public-auth-links">
          <Link to="/login">Sign in</Link>
          <Link className="public-primary-link" to="/register">
            Create account
          </Link>
        </div>
      </nav>
    </header>
  )
}

function PublicFooter() {
  return (
    <footer className="public-footer">
      <div>
        <strong>Myna</strong>
        <p>Private conversations. Real connections.</p>
      </div>
      <nav aria-label="Myna footer navigation">
        {navLinks.slice(1).map((link) => (
          <Link key={link.href} to={link.href}>
            {link.label}
          </Link>
        ))}
      </nav>
    </footer>
  )
}

export function PublicPage({ pageKey }: { pageKey: PublicPageKey }) {
  const page = pages[pageKey]
  const isHome = pageKey === "home"
  const jsonLd = isHome
    ? [
        {
          "@context": "https://schema.org",
          "@type": "WebSite",
          name: "Myna",
          alternateName: "Myna Messaging",
          url: absoluteUrl("/"),
          description: homepageDescription,
        },
        {
          "@context": "https://schema.org",
          "@type": "WebApplication",
          name: "Myna",
          applicationCategory: "CommunicationApplication",
          operatingSystem: "Web",
          url: absoluteUrl("/"),
          description: homepageDescription,
        },
      ]
    : undefined

  return (
    <div className="public-page">
      <SeoMeta
        canonicalPath={page.path}
        description={page.description}
        jsonLd={jsonLd}
        title={page.title}
      />
      <PublicNav />
      <main className="public-main">
        <section className="public-hero">
          <p className="public-eyebrow">Private conversations. Real connections.</p>
          <h1>{page.h1}</h1>
          <p className="public-intro">
            {isHome ? homepageDescription : page.description}
          </p>
          {isHome ? (
            <div className="public-hero-actions">
              <Link className="public-primary-link" to="/register">
                Create account
              </Link>
              <Link to="/login">Sign in</Link>
            </div>
          ) : null}
        </section>

        <section className="public-section-grid" aria-label={`${page.h1} details`}>
          {page.sections.map((section) => (
            <article key={section.title}>
              <h2>{section.title}</h2>
              <p>{section.body}</p>
            </article>
          ))}
        </section>
      </main>
      <PublicFooter />
    </div>
  )
}

export function NotFoundPage() {
  return (
    <div className="public-page">
      <SeoMeta
        canonicalPath="/404"
        description="The requested Myna page was not found."
        robots="noindex, nofollow"
        title="Page Not Found - Myna"
      />
      <PublicNav />
      <main className="public-main public-error-main">
        <section className="public-hero">
          <p className="public-eyebrow">404</p>
          <h1>Page not found</h1>
          <p className="public-intro">
            The page you requested could not be found. Return to the Myna
            homepage to continue browsing public information.
          </p>
          <div className="public-hero-actions">
            <Link className="public-primary-link" to="/">
              Go to homepage
            </Link>
          </div>
        </section>
      </main>
      <PublicFooter />
    </div>
  )
}
