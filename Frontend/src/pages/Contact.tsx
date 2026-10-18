import { CodeXml, MessageCircle, TriangleAlert } from "lucide-react";

import { PageHeader } from "../components/PageHeader";
import { useWhatsapp } from "../hooks/useWhatsapp";
import { PublicShell } from "../components/PublicShell";
import { BRAND } from "../lib/brand";

/**
 * How to reach the team.
 *
 * There is deliberately no office address, no landline and no support inbox,
 * because inventing one would be the exact failure AGENTS.md 17 #10 warns
 * about: a page that makes a prototype look like an organisation with a front
 * desk. What exists is a WhatsApp number and four students, so that is what
 * this page offers.
 *
 * The number comes from the backend's WHATSAPP_PUBLIC_NUMBER rather than
 * being written here. The repository is public (AGENTS.md 12), and one
 * source of truth means the button, the QR and the number people message
 * cannot drift apart.
 */


const REPO = "https://github.com/SalmanZulfiqarShaikh/CodeConnect-UBIT";

const TEAM = [
  { name: "Salman", role: "Backend, WhatsApp pipeline, infrastructure" },
  { name: "Hussain", role: "Frontend, control room" },
  { name: "Abdul Rehman", role: "Frontend, public pages" },
  { name: "Usaim", role: "Team member" },
];

export default function Contact() {
  const { url, display } = useWhatsapp();

  return (
    <PublicShell>
      <PageHeader kicker="Contact" title="Getting in touch">
        One number for help, a repository for everything else. There is no support desk
        behind this &mdash; it is four students and a prototype.
      </PageHeader>

      <div className="mx-auto w-full max-w-3xl px-4 py-12 sm:px-6 sm:py-14">
        <div
          role="note"
          className="mt-6 flex gap-3 rounded-sm border border-sz-crit/40 bg-sz-crit/8 p-4"
        >
          <TriangleAlert className="mt-0.5 h-4 w-4 shrink-0 text-sz-crit" aria-hidden="true" />
          <p className="max-w-[62ch] text-sz-text">
            <strong className="font-semibold">If you need help right now</strong>, do not
            use this page. Message {BRAND} on WhatsApp, and for a fire or medical emergency
            call the official emergency number first.
          </p>
        </div>

        <h2 className="mt-12 text-[1.5rem] font-semibold tracking-[-0.02em]">Ask for help</h2>
        <p className="mt-2 max-w-[62ch] text-sz-text-2">
          One number, for everything. No account, no form.
        </p>
        <a
          href={url}
          className="mt-4 inline-flex min-h-12 items-center gap-2.5 rounded-sm bg-sz-whatsapp px-5 py-3.5 text-base font-semibold text-white transition-opacity hover:opacity-90"
        >
          <MessageCircle className="h-5 w-5" aria-hidden="true" />
          Message {BRAND} on WhatsApp
        </a>
        {display ? (
          <p className="mt-3 font-mono text-sm text-sz-text-2">{display}</p>
        ) : (
          <p className="mt-3 text-sm text-sz-text-3">
            The public number is not set on this deployment yet.
          </p>
        )}

        <h2 className="mt-12 text-[1.5rem] font-semibold tracking-[-0.02em]">About the project</h2>
        <p className="mt-2 max-w-[62ch] text-sz-text-2">
          {BRAND} is a prototype built for CODE//CONNECT&rsquo;26 at UBIT by team Nova
          Strike. It is not a company and there is no support desk behind it &mdash; for
          anything about how it works, the code and its documented limits are public.
        </p>
        <a
          href={REPO}
          className="mt-4 inline-flex items-center gap-2 text-sz-water underline underline-offset-2"
        >
          <CodeXml className="h-4 w-4" aria-hidden="true" />
          Read the source on GitHub
        </a>

        <h2 className="mt-12 text-[1.5rem] font-semibold tracking-[-0.02em]">The team</h2>
        <ul className="mt-4 flex flex-col divide-y divide-sz-line-soft border-y border-sz-line-soft">
          {TEAM.map((member) => (
            <li key={member.name} className="flex flex-wrap gap-x-4 gap-y-1 py-3">
              <span className="w-32 font-medium text-sz-text">{member.name}</span>
              <span className="text-sz-text-2">{member.role}</span>
            </li>
          ))}
        </ul>

        <h2 className="mt-12 text-[1.5rem] font-semibold tracking-[-0.02em]">Coordinators</h2>
        <p className="mt-2 max-w-[62ch] text-sz-text-2">
          If you are running a response and have been given an account, the control room is
          at{" "}
          <a href="/login" className="text-sz-water underline underline-offset-2">
            /login
          </a>
          .
        </p>
      </div>
    </PublicShell>
  );
}
