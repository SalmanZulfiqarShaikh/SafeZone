import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { useState } from "react";
import { ChevronDown } from "lucide-react";

import { PageHeader } from "../components/PageHeader";
import { PublicShell } from "../components/PublicShell";
import { BRAND } from "../lib/brand";
import { cn } from "../lib/utils";

/**
 * The questions someone actually asks before trusting this with their
 * address at two in the morning.
 *
 * Several answers are uncomfortable -- that volunteers are not vetted, that
 * we cannot send an ambulance, that a dead phone network takes this down with
 * it. They stay. Someone who finds out mid-emergency that the tool cannot do
 * what they assumed is worse off than someone who knew beforehand.
 */

const FAQS: Array<{ q: string; a: string }> = [
  {
    q: "Do I need to register before I can ask for help?",
    a: "No. Anyone can message the WhatsApp number with no account, no code and no form, and get the full response. Registration exists only so we can send you early warnings for your area — it is never a condition of being helped.",
  },
  {
    q: "What should I write in my first message?",
    a: "Where you are, what is happening, and who is with you. An area name is enough if you cannot share a location pin. Mentioning anyone who cannot move on their own — elderly, injured, a small child — matters, because that is what moves a case up the queue. Write it however is fastest for you: English, Urdu, Roman Urdu or mixed are all fine.",
  },
  {
    q: "What happens to my phone number and my address?",
    a: "Your area and a one-line summary go to nearby volunteers so they can decide whether to accept. Your name, number and exact location are released only to the one volunteer who accepts, and only after we have told you. Coordinators see the queue without your contact details attached.",
  },
  {
    q: "Is this an emergency service? Can you send an ambulance?",
    a: `No, and this is the most important answer on this page. ${BRAND} cannot send a boat, an ambulance or a fire crew. For fire and medical emergencies the first thing you get back is the official emergency number, and you should call it. What this does is make sure the right people know about you, in the right order, with everything they need.`,
  },
  {
    q: "Who are the volunteers?",
    a: "Neighbours who signed up. In this prototype the pool is the team's own phones, labelled as demo volunteers everywhere they appear. They are not vetted, trained or insured, and they are asked to assess from a safe place rather than attempt a rescue. A real deployment would need all three of those things.",
  },
  {
    q: "How do you decide who gets help first?",
    a: "A score built from how urgent the situation is, how confident we are that we read the message correctly, and who is at risk. Someone elderly and alone on a ground floor with water rising ranks above a report where nobody vulnerable is named. The reasoning is written out in plain words next to every case, so a coordinator can look at it and disagree.",
  },
  {
    q: "What if several of us report the same thing?",
    a: "They become one case with several reports behind it, not several cases competing for the same boat. Reports close together in time and place, in the same category, are merged automatically — and a merge never lowers the urgency.",
  },
  {
    q: "Does a computer decide, or a person?",
    a: "A person. The system reads, ranks and prepares, but nothing goes out to a volunteer or a responder until a coordinator approves it. That step is deliberately not automated.",
  },
  {
    q: "What if the mobile network is down?",
    a: "Then this does not reach you, and that is a real gap rather than a detail. Everything runs over WhatsApp, with no SMS or USSD fallback, and the system needs its own connection to work at all. Networks fail during exactly the events this is built for.",
  },
  {
    q: "How do I stop getting messages?",
    a: "Reply STOP and the area alerts stop.",
  },
  {
    q: "Does it cost anything?",
    a: "No. It costs whatever your WhatsApp messages normally cost you, which for most people is nothing beyond data.",
  },
];

function Item({ q, a }: { q: string; a: string }) {
  const [open, setOpen] = useState(false);
  const reduceMotion = useReducedMotion();

  return (
    <li className="border-b border-sz-line-soft last:border-0">
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        aria-expanded={open}
        className="flex w-full cursor-pointer items-start justify-between gap-4 py-4 text-left transition-colors hover:text-sz-water"
      >
        <span className="font-medium">{q}</span>
        <ChevronDown
          aria-hidden="true"
          className={cn(
            "mt-0.5 h-4 w-4 shrink-0 text-sz-text-3 transition-transform duration-300",
            open && "rotate-180",
          )}
        />
      </button>

      {/* Height animates so the answer unfolds rather than appearing and
          shoving the rest of the list down a step. Motion that answers a
          click is the kind worth having. */}
      <AnimatePresence initial={false}>
        {open && (
          <motion.div
            key="answer"
            initial={reduceMotion ? false : { height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={reduceMotion ? undefined : { height: 0, opacity: 0 }}
            transition={{ duration: reduceMotion ? 0 : 0.28, ease: [0.22, 1, 0.36, 1] }}
            className="overflow-hidden"
          >
            <p className="max-w-[62ch] pb-5 text-sz-text-2">{a}</p>
          </motion.div>
        )}
      </AnimatePresence>
    </li>
  );
}

export default function Faq() {
  return (
    <PublicShell>
      <PageHeader kicker="Questions" title="Frequently asked">
        If your question is not here, message us on WhatsApp &mdash; but if you need help
        right now, do not wait for an answer to a question. Just send what is happening.
      </PageHeader>

      <div className="mx-auto w-full max-w-3xl px-4 py-12 sm:px-6 sm:py-14">
        <ul className="overflow-hidden rounded-lg border border-sz-line bg-sz-panel px-5">
          {FAQS.map((item) => (
            <Item key={item.q} {...item} />
          ))}
        </ul>
      </div>
    </PublicShell>
  );
}
