import { CodeXml, ShieldCheck, TriangleAlert } from "lucide-react";
import { FaGithub, FaWhatsapp } from "react-icons/fa6";
import { QRCodeSVG } from "qrcode.react";

import { PageHeader } from "../components/PageHeader";
import { PublicShell } from "../components/PublicShell";
import { Reveal } from "../components/Reveal";
import { BRAND } from "../lib/brand";
import { useWhatsapp } from "../hooks/useWhatsapp";

/**
 * How to reach us.
 *
 * There is deliberately no office address, no landline and no support inbox,
 * because inventing one would be the failure AGENTS.md 17 #10 warns about: a
 * page that makes a prototype look like an organisation with a front desk.
 * What exists is a WhatsApp number and four students, so that is the page --
 * and the number is given the weight it deserves rather than a line of text,
 * because it is the only way anyone here actually gets help.
 *
 * The number comes from the backend's WHATSAPP_PUBLIC_NUMBER rather than
 * being written here. The repository is public (AGENTS.md 12), and one
 * source of truth means the button, the QR and the number cannot drift.
 */

const REPO = "https://github.com/SalmanZulfiqarShaikh/CodeConnect-UBIT";

const TEAM = [
  { name: "Salman", role: "Backend, WhatsApp pipeline, infrastructure", url: "https://github.com/SalmanZulfiqarShaikh" },
  { name: "Hussain", role: "Frontend, control room", url: "https://github.com/hussainabbas6706" },
  { name: "Abdul Rehman", role: "Frontend, public pages", url: "https://github.com/mabdulrehmankhan666" },
  { name: "Usaim", role: "Frontend", url: "https://github.com/usaim35" },
];

export default function Contact() {
  const { url, display } = useWhatsapp();

  return (
    <PublicShell>
      <PageHeader kicker="Contact" title="Getting in touch">
        One number for help, a repository for everything else. There is no support desk
        behind this &mdash; it is four students and a prototype.
      </PageHeader>

      <div className="mx-auto w-full max-w-5xl px-4 py-10 sm:px-6">
        {/* ─── The number, given the room it deserves ───────────────── */}
        <Reveal>
          <section className="overflow-hidden rounded-xl border border-sz-whatsapp/35 bg-sz-whatsapp/8">
            <div className="grid gap-8 p-6 sm:p-8 lg:grid-cols-[minmax(0,1fr)_auto] lg:items-center lg:gap-12">
              <div>
                <p className="flex items-center gap-2 text-[13px] font-medium text-sz-whatsapp">
                  <FaWhatsapp className="h-4 w-4" aria-hidden="true" />
                  Ask for help
                </p>
                <h2 className="mt-2 text-[1.75rem] leading-tight font-semibold tracking-[-0.025em] sm:text-[2.1rem]">
                  One number, for everything
                </h2>
                <p className="mt-3 max-w-[46ch] text-sz-text-2">
                  Flood, fire, medical, trapped, no food or water. No account, no form,
                  nothing to install &mdash; any number, day or night.
                </p>

                <div className="mt-6 flex flex-wrap items-center gap-x-5 gap-y-3">
                  <a
                    href={url}
                    className="inline-flex min-h-13 items-center gap-3 rounded-sm bg-sz-whatsapp px-6 text-[17px] font-semibold text-white transition-opacity hover:opacity-90"
                  >
                    <FaWhatsapp className="h-6 w-6" aria-hidden="true" />
                    Message {BRAND}
                  </a>
                  {display && (
                    <p className="font-mono text-[15px] text-sz-text-2">{display}</p>
                  )}
                </div>
              </div>

              {/* The QR earns its place here: this page gets opened on a
                  laptop and acted on from a phone. */}
              <div className="flex items-center gap-4 lg:flex-col lg:gap-3">
                {url ? (
                  <span className="rounded-sm bg-white p-2.5">
                    <QRCodeSVG value={url} size={116} level="M" marginSize={0} />
                  </span>
                ) : (
                  <span
                    aria-hidden="true"
                    className="sz-hatch block h-[136px] w-[136px] rounded-sm border border-sz-line text-sz-line"
                  />
                )}
                <p className="max-w-[16ch] text-[13px] text-sz-text-2 lg:text-center">
                  {url ? "Scan to open WhatsApp" : "Number not set on this deployment"}
                </p>
              </div>
            </div>

            <p className="flex items-start gap-2.5 border-t border-sz-whatsapp/25 bg-sz-crit/8 px-6 py-3.5 text-[14px] text-sz-text sm:px-8">
              <TriangleAlert
                className="mt-0.5 h-4 w-4 shrink-0 text-sz-crit"
                aria-hidden="true"
              />
              <span>
                <strong className="font-semibold">Needing help right now?</strong> Use the
                number above, not this page &mdash; and for a fire or medical emergency
                call the official number first.
              </span>
            </p>
          </section>
        </Reveal>

        {/* ─── Team ─────────────────────────────────────────────────── */}
        <Reveal delay={0.06}>
          <div className="mt-12 flex flex-wrap items-baseline justify-between gap-x-6 gap-y-1">
            <h2 className="text-[1.5rem] font-semibold tracking-[-0.02em]">Who built it</h2>
            <p className="text-sz-text-2">
              Team Nova Strike &middot; CODE//CONNECT&rsquo;26 at UBIT
            </p>
          </div>
        </Reveal>

        <ul className="mt-5 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {TEAM.map((member, index) => (
            <Reveal key={member.name} delay={index * 0.05}>
              <a
                href={member.url}
                target="_blank"
                rel="noreferrer noopener"
                className="group flex h-full flex-col rounded-lg border border-sz-line bg-sz-panel p-5 transition-colors hover:border-sz-water/55"
              >
                <span className="flex h-12 w-12 items-center justify-center rounded-full border border-sz-line bg-sz-base text-lg font-semibold text-sz-text-2 transition-colors group-hover:border-sz-water/50 group-hover:text-sz-water">
                  {member.name.charAt(0)}
                </span>
                <span className="mt-3.5 flex items-center gap-2 font-semibold">
                  {member.name}
                  <FaGithub
                    className="h-3.5 w-3.5 text-sz-text-3 transition-colors group-hover:text-sz-water"
                    aria-hidden="true"
                  />
                </span>
                <span className="mt-1 text-[13.5px] leading-relaxed text-sz-text-2">
                  {member.role}
                </span>
              </a>
            </Reveal>
          ))}
        </ul>

        {/* ─── Everything else ──────────────────────────────────────── */}
        <div className="mt-6 grid gap-4 sm:grid-cols-2">
          <Reveal delay={0.06}>
            <a
              href={REPO}
              target="_blank"
              rel="noreferrer noopener"
              className="group flex h-full items-start gap-4 rounded-lg border border-sz-line bg-sz-panel p-5 transition-colors hover:border-sz-water/55"
            >
              <CodeXml className="mt-0.5 h-5 w-5 shrink-0 text-sz-water" aria-hidden="true" />
              <span>
                <span className="block font-semibold">Read the source</span>
                <span className="mt-1 block text-[14px] leading-relaxed text-sz-text-2">
                  Every limit on the About page is in the code and the commit history.
                  Nothing here is a mock-up.
                </span>
              </span>
            </a>
          </Reveal>

          <Reveal delay={0.12}>
            <a
              href="/login"
              className="group flex h-full items-start gap-4 rounded-lg border border-sz-line bg-sz-panel p-5 transition-colors hover:border-sz-elev/55"
            >
              <ShieldCheck className="mt-0.5 h-5 w-5 shrink-0 text-sz-elev" aria-hidden="true" />
              <span>
                <span className="block font-semibold">Coordinators</span>
                <span className="mt-1 block text-[14px] leading-relaxed text-sz-text-2">
                  If you are running a response and have an account, the control room is
                  through here.
                </span>
              </span>
            </a>
          </Reveal>
        </div>
      </div>
    </PublicShell>
  );
}
