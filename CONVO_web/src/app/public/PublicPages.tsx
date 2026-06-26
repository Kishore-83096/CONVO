import { Link } from "react-router"

import SeoMeta from "@/app/seo/SeoMeta"
import { absoluteUrl } from "@/app/seo/seo-url"
import convoLogo from "@/assets/convo/CONVO.png"

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
  "CONVO is a modern real-time messaging application for private conversations, instant message delivery, contact management, and simple communication."

const pages: Record<PublicPageKey, PublicPageContent> = {
  home: {
    path: "/",
    title: "CONVO - Secure Real-Time Messaging Application",
    description: homepageDescription,
    h1: "Secure Real-Time Messaging with CONVO",
    sections: [
      {
        title: "What CONVO is",
        body: "CONVO is a modern real-time messaging application designed for private conversations, instant communication, contact management, and a simple messaging experience.",
      },
      {
        title: "Real-time messaging",
        body: "CONVO provides a focused chat workspace for quick conversations and message workflows in a clean browser-based interface.",
      },
      {
        title: "Contact management",
        body: "Users can find contacts, save people they communicate with, rename saved contacts, and keep conversations organized.",
      },
      {
        title: "Privacy and security",
        body: "CONVO uses authenticated sessions for private areas of the application and keeps personal chat screens out of the public sitemap.",
      },
      {
        title: "Simple user experience",
        body: "The interface is designed to make account creation, sign in, profile management, and messaging feel direct and easy to navigate.",
      },
      {
        title: "Sign in",
        body: "Existing users can sign in from the public navigation to access their private CONVO workspace.",
      },
      {
        title: "Create account",
        body: "New users can create a CONVO identity and start setting up their profile and contacts.",
      },
    ],
  },
  features: {
    path: "/features",
    title: "CONVO Features - Real-Time Messaging and Contact Management",
    description:
      "Explore CONVO features for real-time messaging, contact management, profiles, and a simple communication workspace.",
    h1: "CONVO features for messaging and contacts",
    sections: [
      {
        title: "Messaging workspace",
        body: "CONVO gives users a dedicated space for conversations, message composition, and contact-based communication.",
      },
      {
        title: "Saved contacts",
        body: "Contact tools help users search, save, rename, view, and remove contacts from their personal workspace.",
      },
      {
        title: "Profile tools",
        body: "Users can manage profile details, profile pictures, address information, and important events after signing in.",
      },
    ],
  },
  security: {
    path: "/security",
    title: "Security and Privacy - CONVO",
    description:
      "Learn how CONVO separates public information from authenticated messaging, profile, account, and contact pages.",
    h1: "Security and privacy in CONVO",
    sections: [
      {
        title: "Authenticated private pages",
        body: "Messaging, profile, account, and contact screens are treated as private application areas and are excluded from the public sitemap.",
      },
      {
        title: "Session-based access",
        body: "CONVO uses authenticated sessions to protect private app screens. Search engine metadata is not used as a replacement for authorization.",
      },
      {
        title: "Careful public content",
        body: "Public SEO pages describe the product without exposing private user information, contact data, or chat content.",
      },
    ],
  },
  privacy: {
    path: "/privacy",
    title: "Privacy Policy - CONVO",
    description:
      "Read CONVO privacy information about public pages, account data, contacts, and private messaging areas.",
    h1: "CONVO privacy policy",
    sections: [
      {
        title: "Public website pages",
        body: "CONVO public pages contain product information and links for visitors. They do not publish authenticated chat content.",
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
    title: "About CONVO - Real-Time Messaging Application",
    description:
      "About CONVO, a web-based real-time messaging application for private conversations and contact management.",
    h1: "About CONVO",
    sections: [
      {
        title: "Built for conversations",
        body: "CONVO is a browser-based messaging application focused on private communication, clean navigation, and everyday contact workflows.",
      },
      {
        title: "Product direction",
        body: "The app brings account identity, profiles, contacts, and chat screens into one consistent user experience.",
      },
    ],
  },
  contact: {
    path: "/contact",
    title: "Contact CONVO",
    description:
      "Contact CONVO for questions about the messaging application, accounts, privacy, or support.",
    h1: "Contact CONVO",
    sections: [
      {
        title: "Support",
        body: "For production, add the official CONVO support email, business address, or contact form endpoint here.",
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
      <nav className="public-nav" aria-label="CONVO public navigation">
        <Link className="public-brand" to="/">
          <img
            src={convoLogo}
            alt="CONVO logo"
            width="42"
            height="42"
          />
          <span>CONVO</span>
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
        <strong>CONVO</strong>
        <p>Secure real-time messaging for private conversations.</p>
      </div>
      <nav aria-label="CONVO footer navigation">
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
          "@type": "WebApplication",
          name: "CONVO",
          applicationCategory: "CommunicationApplication",
          operatingSystem: "Web",
          url: absoluteUrl("/"),
          description: homepageDescription,
        },
        {
          "@context": "https://schema.org",
          "@type": "WebSite",
          name: "CONVO",
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
          <p className="public-eyebrow">CONVO messaging application</p>
          <h1>{page.h1}</h1>
          {isHome ? (
            <p className="public-intro">{homepageDescription}</p>
          ) : (
            <p className="public-intro">{page.description}</p>
          )}
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
        description="The requested CONVO page was not found."
        robots="noindex, nofollow"
        title="Page Not Found - CONVO"
      />
      <PublicNav />
      <main className="public-main public-error-main">
        <section className="public-hero">
          <p className="public-eyebrow">404</p>
          <h1>Page not found</h1>
          <p className="public-intro">
            The page you requested could not be found. Return to the CONVO
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
