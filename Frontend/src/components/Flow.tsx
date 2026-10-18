import { motion, useReducedMotion } from "framer-motion";
import {
  ArrowDown,
  ArrowRight,
  HeartHandshake,
  Headset,
  MessageCircleReply,
  ShieldCheck,
} from "lucide-react";
import { FaWhatsapp } from "react-icons/fa6";
import type { ComponentType } from "react";

import { Reveal } from "./Reveal";
import { BRAND } from "../lib/brand";
import rescue from "../assets/photos/rescue-1122.png";

/**
 * One message, start to finish, drawn as the path a case actually takes.
 *
 * The branches are where this gets interesting, and both are drawn the way
 * the system really behaves rather than the way a tidy diagram would prefer:
 *
 * * **After the message** it forks three ways at once -- the person gets an
 *   automatic reply, the nearest on-duty neighbours are offered the case,
 *   and a coordinator is alerted. None of those waits for a human.
 * * **Only the official handoff waits for approval.** A neighbour is being
 *   *asked*: the offer carries an area and a one-line summary, no name and
 *   no number, and anyone can decline, so a misread message costs a walk.
 *   Putting an ambulance, a fire crew or the police on the road spends
 *   something the city has few of, so that half keeps a human in it.
 *
 * The approval gate therefore sits on one branch rather than across the
 * whole line, which is the honest drawing: most of this page happens
 * whether or not a coordinator is awake.
 */

type Node = {
  icon?: ComponentType<{ className?: string; "aria-hidden"?: boolean }>;
  logo?: string;
  title: string;
  body: string;
  ring: string;
  tone: string;
};

const START: Node = {
  icon: FaWhatsapp,
  title: "You message us",
  body: "Any number. No account.",
  ring: "border-sz-whatsapp/45 bg-sz-whatsapp/10",
  tone: "text-sz-whatsapp",
};

/** Everything on this fork happens at once, in seconds, with nobody's
 *  permission. */
const FIRST_FORK: Node[] = [
  {
    icon: MessageCircleReply,
    title: "You get an answer",
    body: "Safety steps and the official number, in seconds.",
    ring: "border-sz-water/45 bg-sz-water/10",
    tone: "text-sz-water",
  },
  {
    icon: HeartHandshake,
    title: "Neighbours are asked",
    body: "Nearest on-duty neighbours, straight away. Your area only — no name, no number.",
    ring: "border-sz-earth/45 bg-sz-earth/10",
    tone: "text-sz-earth",
  },
  {
    icon: Headset,
    title: "A coordinator is alerted",
    body: "Scored on urgency and who is at risk. Duplicates merged.",
    ring: "border-sz-water/45 bg-sz-water/10",
    tone: "text-sz-water",
  },
];

const GATE: Node = {
  icon: ShieldCheck,
  title: "A coordinator approves the handoff",
  body: "The one step that waits for a human.",
  ring: "border-sz-elev/50 bg-sz-elev/12",
  tone: "text-sz-elev",
};

const DESTINATION: Node = {
  logo: rescue,
  title: "Rescue 1122",
  body: "Medical, fire and trapped-person cases, already filled in.",
  ring: "border-sz-line bg-sz-base",
  tone: "",
};

function Circle({ node, size = "md" }: { node: Node; size?: "md" | "lg" }) {
  const box = size === "lg" ? "h-13 w-13" : "h-11 w-11";
  const glyph = size === "lg" ? "h-5.5 w-5.5" : "h-[18px] w-[18px]";

  return (
    <span
      className={`flex ${box} shrink-0 items-center justify-center rounded-full border-2 ${node.ring}`}
    >
      {node.logo ? (
        <img src={node.logo} alt="" loading="lazy" className="h-[72%] w-[72%] object-contain" />
      ) : node.icon ? (
        <node.icon className={`${glyph} ${node.tone}`} aria-hidden />
      ) : null}
    </span>
  );
}

function Step({ node, size }: { node: Node; size?: "md" | "lg" }) {
  return (
    <div className="flex items-center gap-3 lg:w-[13.5rem]">
      <Circle node={node} size={size} />
      <div className="min-w-0">
        <p className="text-[13.5px] font-semibold leading-tight">{node.title}</p>
        <p className="mt-0.5 text-[12px] leading-snug text-sz-text-2">{node.body}</p>
      </div>
    </div>
  );
}

/** A connector that shows direction. The dot travels the line on a loop, so
 *  the diagram reads as a flow rather than a row of boxes. */
function Connector({ label }: { label?: string }) {
  const reduceMotion = useReducedMotion();

  return (
    <div
      className="flex shrink-0 items-center justify-center gap-1.5 py-1.5 lg:flex-col lg:py-0"
      aria-hidden="true"
    >
      <div className="relative hidden h-px w-6 bg-sz-line lg:block">
        {!reduceMotion && (
          <motion.span
            className="absolute top-1/2 h-1.5 w-1.5 -translate-y-1/2 rounded-full bg-sz-water"
            animate={{ left: ["0%", "100%"], opacity: [0, 1, 1, 0] }}
            transition={{ duration: 1.8, repeat: Infinity, ease: "linear" }}
          />
        )}
      </div>
      <ArrowRight className="hidden h-4 w-4 text-sz-text-3 lg:block" />
      <ArrowDown className="h-5 w-5 text-sz-text-3 lg:hidden" />
      {label && <span className="sr-only">{label}</span>}
    </div>
  );
}

/** The two or three nodes a fork opens into, bracketed so the split reads as
 *  one moment rather than a list that happens to be stacked. */
function Fork({ nodes }: { nodes: Node[] }) {
  return (
    <div className="relative flex flex-col gap-2.5 lg:border-l-2 lg:border-sz-line lg:py-1 lg:pl-3">
      {nodes.map((node, index) => (
        <Reveal key={node.title} delay={index * 0.08}>
          <Step node={node} />
        </Reveal>
      ))}
    </div>
  );
}

export function Flow() {
  return (
    <section className="border-y border-sz-line bg-sz-panel">
      <div className="mx-auto w-full max-w-6xl px-4 py-14 sm:px-6 sm:py-16">
        <Reveal>
          <h2 className="text-[1.6rem] font-semibold tracking-[-0.025em] sm:text-[2rem]">
            What happens when you message
          </h2>
          <p className="mt-2.5 max-w-[64ch] text-[15px] text-sz-text-2">
            One message in, a finished case out. {BRAND} reads and ranks, a person
            approves the handoff, and whoever goes gets everything they need.
          </p>
        </Reveal>

        {/* Held to a narrower measure than the heading above it and centred.
            Stretched across the full container the nodes drift apart and the
            arrows between them read as gaps rather than as a sequence. The
            node sizes are unchanged -- this is composition, not scale. */}
        <div className="mt-9 flex flex-col items-start gap-1 lg:mx-auto lg:max-w-5xl lg:flex-row lg:items-center lg:justify-between lg:gap-0">
          <Reveal>
            <Step node={START} size="lg" />
          </Reveal>

          <Connector label="leads to" />
          <Fork nodes={FIRST_FORK} />
          <Connector label="then" />

          <Reveal delay={0.1}>
            <Step node={GATE} size="lg" />
          </Reveal>

          <Connector label="which sends it to" />

          <Reveal delay={0.18}>
            <div className="flex flex-col gap-2">
              <Step node={DESTINATION} />
              <p className="max-w-[20rem] pl-[3.5rem] text-[11px] leading-snug text-sz-text-3 lg:w-[13.5rem]">
                Where cases are routed. Not affiliated with this service.
              </p>
            </div>
          </Reveal>
        </div>

      </div>
    </section>
  );
}
