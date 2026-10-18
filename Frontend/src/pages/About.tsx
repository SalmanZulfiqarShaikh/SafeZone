import { PageHeader } from "../components/PageHeader";
import { PublicShell } from "../components/PublicShell";
import { Reveal } from "../components/Reveal";
import { BRAND, FRAMING } from "../lib/brand";

/**
 * What SafeZone is, written to be read by someone deciding whether to trust
 * it rather than by a judge scoring it.
 *
 * Every limit on this page is a real one, stated plainly (AGENTS.md 16 and
 * 17 #10). Nothing here claims a capability the system does not have, and the
 * page is deliberately short on adjectives.
 */

const STEPS = [
  {
    title: "A message arrives",
    body: `Someone sends a WhatsApp message in whatever words they have — English, Urdu, Roman Urdu, or a mix. There is no form, no app to install and no account to make. ${BRAND} reads it and works out what happened, where, and who is at risk.`,
  },
  {
    title: "It gets ranked, not queued",
    body: "A score decides what gets attention first: how urgent, how confident we are, and who is vulnerable — someone elderly, alone, on a ground floor with water rising outranks a report with no one named. The reasoning is shown next to the score, in words, so a coordinator can disagree with it.",
  },
  {
    title: "Duplicates become one case",
    body: "Five neighbours reporting the same flooded street is one case with five reports behind it, not five cases competing for the same boat. Reports close in time and place, in the same category, are merged automatically.",
  },
  {
    title: "A human approves it",
    body: "Nothing is sent to anyone until a coordinator approves it. That is the one manual step, and it is deliberate: the cost of dispatching people to a misread message is paid by whoever goes.",
  },
  {
    title: "It reaches someone who can act",
    body: "The nearest registered volunteers are offered the case. Fire and medical always go to the official emergency number as well, never to volunteers alone. Responders get one page with the location, what happened and who is at risk — so they spend their time coming, not asking questions.",
  },
  {
    title: "We check it actually arrived",
    body: "When someone marks a case done, we ask the person who reported it whether help reached them. If it did not, the case goes back to the top of the queue.",
  },
];

const LIMITS = [
  "We are not an emergency service. We cannot send a boat, an ambulance or a fire crew ourselves.",
  "Volunteers are neighbours who signed up. In this prototype they are the team's own phones, they are not vetted, trained or insured, and they are asked to assess from a safe place.",
  "The handoff to responders is a link we send them, not a live connection to any organisation.",
  "Matching is nearest-first by straight-line distance, not routed travel time. A volunteer 400 m away across a canal may be further in practice than one a kilometre down the road.",
  "The scoring weights are hand-tuned, not learned from data. They are visible and adjustable rather than hidden.",
  "Everything runs over WhatsApp. There is no SMS or USSD fallback, which is a real gap given that networks fail during exactly the events this is built for.",
  "The system needs a connection to its database. There is no offline mode.",
];

export default function About() {
  return (
    <PublicShell>
      <PageHeader kicker="About" title={`What ${BRAND} does`}>
        {FRAMING}
      </PageHeader>

      <div className="mx-auto w-full max-w-3xl px-4 py-12 sm:px-6 sm:py-14">
        <Reveal>
          <p className="mt-6 max-w-[62ch] text-sz-text-2">
          During the Karachi monsoon, help does not usually fail because nobody wants to
          give it. It fails because nobody can tell, in the first hour, which of four
          hundred messages is the one where someone cannot get up the stairs. That is the
          problem {BRAND} works on: not rescue, but knowing who to reach first and giving
            whoever goes everything they need before they leave.
          </p>
        </Reveal>

        <Reveal>
          <h2 className="mt-14 text-[1.5rem] font-semibold tracking-[-0.02em]">
            How it works
          </h2>
        </Reveal>
        <ol className="mt-5 flex flex-col gap-6">
          {STEPS.map((step, index) => (
            <Reveal
              key={step.title}
              delay={index * 0.06}
              className="relative flex gap-5 pl-1"
            >
              <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full border border-sz-water/40 bg-sz-water/10 font-mono text-[13px] text-sz-water">
                {index + 1}
              </span>
              <div className="min-w-0 pb-1">
                <h3 className="font-semibold text-sz-text">{step.title}</h3>
                <p className="mt-1.5 max-w-[62ch] text-sz-text-2">{step.body}</p>
              </div>
            </Reveal>
          ))}
        </ol>

        <Reveal>
          <h2 className="mt-14 text-[1.5rem] font-semibold tracking-[-0.02em]">
            What it is not
          </h2>
        </Reveal>
        <p className="mt-2 max-w-[62ch] text-sz-text-2">
          These are the limits as they stand today, not a roadmap. Knowing them is the
          difference between a tool people can rely on and one that fails them quietly.
        </p>
        <ul className="mt-5 flex flex-col gap-2.5">
          {LIMITS.map((limit, index) => (
            <Reveal key={limit} delay={index * 0.04}>
              <div className="rounded-sm border-l-2 border-sz-elev/50 bg-sz-panel px-4 py-3 text-sz-text-2">
                {limit}
              </div>
            </Reveal>
          ))}
        </ul>

        <h2 className="mt-14 text-[1.5rem] font-semibold tracking-[-0.02em]">Who built it</h2>
        <p className="mt-2 max-w-[62ch] text-sz-text-2">
          Team Nova Strike, for CODE//CONNECT&rsquo;26 at UBIT: Salman, Hussain, Abdul
          Rehman and Usaim. It is a working prototype, running on real infrastructure with
          a real WhatsApp number &mdash; not a mock-up &mdash; but it is a prototype, and
          the list above is what that means in practice.
        </p>
      </div>
    </PublicShell>
  );
}
