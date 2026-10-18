import { Link2, Loader2, Phone } from "lucide-react";
import { useState } from "react";

import { BRAND_DOMAIN } from "../../lib/brand";
import { clock, score as fmtScore, timeAgoPhrase } from "../../lib/format";
import {
  CATEGORY_LABEL,
  DISPATCH_LABEL,
  dispatchTone,
  isOfficialFirst,
  OFFER_LABEL,
  offerTone,
  protocolLabels,
  SEVERITY_LABEL,
  SEVERITY_RING,
  SEVERITY_TEXT,
  severityOf,
} from "../../lib/severity";
import type { CaseDetail, Channel, PersonVuln } from "../../lib/types";
import { cn } from "../../lib/utils";
import { SimulatedSwatch } from "../SimulatedTag";
import { StatusPill } from "../StatusPill";
import { ChannelPicker } from "./ChannelPicker";

/** Unanswered vulnerability questions mean unknown, never false — so only
 *  truthy answers become chips. An empty set is not "no vulnerabilities". */
function vulnChips(vuln: PersonVuln | undefined): string[] {
  if (!vuln) return [];
  const chips: string[] = [];
  if (vuln.elderly) chips.push("Elderly");
  if (vuln.alone) chips.push("Alone");
  if (vuln.cannot_move) chips.push("Cannot move");
  if (vuln.children) chips.push("Children present");
  if (typeof vuln.floor === "string" && vuln.floor) {
    chips.push(`${vuln.floor.charAt(0).toUpperCase()}${vuln.floor.slice(1)} floor`);
  }
  return chips;
}

function Section({
  title,
  aside,
  children,
}: {
  title: string;
  aside?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <section className="border-b border-sz-line-soft px-4 py-4 sm:px-5">
      <div className="mb-2.5 flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
        <h3 className="font-medium">{title}</h3>
        {aside}
      </div>
      {children}
    </section>
  );
}

export function ResponsePanel({
  row,
  busy,
  onApprove,
  onReopen,
}: {
  row: CaseDetail | null;
  busy: boolean;
  onApprove: (channel: Channel) => void;
  onReopen: () => void;
}) {
  const category = row?.incident?.category;
  const officialFirst = category ? isOfficialFirst(category) : false;

  // Fire, medical and structural are never volunteer-only, so the default
  // lands on Both rather than quietly leaving the official handoff unmade.
  // Dashboard keys this panel by case id, so opening another case
  // re-initialises the choice instead of carrying the last one over.
  const [channel, setChannel] = useState<Channel>(officialFirst ? "both" : "volunteers");

  if (!row) {
    return (
      <aside className="sz-card m-3 w-full shrink-0 grow basis-96 px-4 py-8 lg:m-3 lg:ml-0 lg:w-auto lg:max-w-md">
        <p className="text-sz-text-2">Pick a case from the feed to see it here.</p>
      </aside>
    );
  }

  const severity = severityOf(row.priority_score);
  // Until extraction has produced a score, there is no severity band to show.
  // Printing "Normal 0.00" on a case that arrived two seconds ago would be a
  // claim the system has not made yet.
  const scored = row.priority_score > 0;
  const incident = row.incident;
  const exact = incident ? incident.location_source === "pin" || incident.location_known : false;
  const chips = vulnChips(row.person?.person_vuln);
  const protocol = protocolLabels(row.protocol_path);
  const link = row.responder_links[0];
  const canDispatch = exact;

  return (
    <aside
      aria-label={`Case ${row.id} detail`}
      className="sz-card sz-scroll m-3 flex min-h-0 w-full shrink-0 grow basis-96 flex-col overflow-y-auto lg:ml-0 lg:w-auto lg:max-w-md"
    >
      <div className="border-b border-sz-line-soft px-4 py-4 sm:px-5">
        <div className="flex items-center justify-between gap-3">
          <h2 className="font-mono text-lg font-medium tracking-[-0.01em]">Case {row.id}</h2>
          {scored ? (
            <StatusPill tone={SEVERITY_RING[severity]} className="px-2 py-1 text-[12px]">
              {SEVERITY_LABEL[severity]}
            </StatusPill>
          ) : (
            <StatusPill
              tone="border-sz-water/45 bg-sz-water/12 text-sz-water"
              className="px-2 py-1 text-[12px]"
            >
              Triaging
            </StatusPill>
          )}
        </div>
        <p className="mt-1.5 flex flex-wrap items-baseline gap-x-2 gap-y-1 text-[12px] text-sz-text-2">
          <span>{category ? CATEGORY_LABEL[category] : "Unknown"}</span>
          <span className="text-sz-line">·</span>
          <span>{row.zone?.name ?? "Area unknown"}</span>
          <span className="text-sz-line">·</span>
          <span>first report {timeAgoPhrase(incident?.first_report_at ?? row.created_at)}</span>
        </p>
        <div className="mt-2.5 flex flex-wrap items-center gap-1.5">
          <StatusPill tone={dispatchTone(row.dispatch_status)}>
            {DISPATCH_LABEL[row.dispatch_status]}
          </StatusPill>
          {row.person?.first_name && (
            <span className="text-[12px] text-sz-text-3">
              Reported by {row.person.first_name}. Contact is released on ACCEPT, not here.
            </span>
          )}
        </div>
        {row.reopened && row.reopen_reason && (
          <p className="mt-3 rounded-sm border border-sz-elev/40 bg-sz-elev/10 px-2.5 py-2 text-[12px] text-sz-elev">
            Re-opened: {row.reopen_reason}
          </p>
        )}
      </div>

      <Section title="Why this ranks here">
        <div className="mb-2.5 flex items-baseline gap-3">
          <span
            className={cn(
              "font-mono text-3xl leading-none font-semibold tracking-[-0.03em]",
              scored ? SEVERITY_TEXT[severity] : "text-sz-text-3",
            )}
          >
            {scored ? fmtScore(row.priority_score) : "—"}
          </span>
          <span className="text-[12px] text-sz-text-3">
            {scored ? "priority score" : "extraction still running"}
          </span>
        </div>
        {row.reason && <p className="max-w-[58ch] text-sz-text-2">{row.reason}</p>}
        <dl className="mt-3.5 flex flex-wrap gap-x-7 gap-y-2.5">
          {[
            { label: "Reports merged", value: String(incident?.report_count ?? 1) },
            { label: "Confidence", value: fmtScore(incident?.confidence) },
            { label: "Urgency", value: fmtScore(incident?.urgency) },
          ].map((stat) => (
            <div key={stat.label}>
              <dt className="text-[12px] text-sz-text-3">{stat.label}</dt>
              <dd className="font-mono text-sm">{stat.value}</dd>
            </div>
          ))}
        </dl>
      </Section>

      <Section
        title="The situation"
        aside={
          !exact ? (
            <StatusPill tone="border-sz-elev/45 bg-sz-elev/12 text-sz-elev">
              Area centre only
            </StatusPill>
          ) : undefined
        }
      >
        {row.vuln_summary && (
          <p className="max-w-[58ch] text-sz-text-2">{row.vuln_summary}</p>
        )}
        {chips.length > 0 && (
          <ul className="mt-3 flex flex-wrap gap-1.5">
            {chips.map((chip) => (
              <li
                key={chip}
                className="rounded-sm border border-sz-line bg-sz-raised px-2 py-0.5 text-[12px] text-sz-text-2"
              >
                {chip}
              </li>
            ))}
          </ul>
        )}
        {protocol.length > 0 && (
          <div className="mt-3.5 flex flex-wrap items-center gap-1.5">
            <span className="text-[12px] text-sz-text-3">Protocol path</span>
            {protocol.map((step) => (
              <span
                key={step}
                className="rounded-sm bg-sz-raised px-1.5 py-0.5 font-mono text-[11px] text-sz-text-2"
              >
                {step}
              </span>
            ))}
          </div>
        )}
      </Section>

      <Section
        title="Dispatch"
        aside={
          row.dispatches.length > 0 ? (
            <span className="text-[12px] text-sz-text-3">
              Ring {Math.max(...row.dispatches.map((d) => d.ring))} · nearest three first
            </span>
          ) : undefined
        }
      >
        {row.dispatches.length === 0 ? (
          <p className="max-w-[58ch] text-[12px] text-sz-text-3">
            {canDispatch
              ? "Nothing offered yet."
              : "This case has no exact pin, so it cannot be offered to a volunteer or sent as a handoff. The bot keeps asking for a location; a phone call is the other way in."}
          </p>
        ) : (
          <ul>
            {row.dispatches.map((dispatch) => (
              <li
                key={dispatch.id}
                className="flex items-center gap-3 border-t border-sz-line-soft py-2.5 first:border-t-0 first:pt-0"
              >
                <SimulatedSwatch className="text-sz-earth" />
                <div className="min-w-0 grow">
                  <p className="flex flex-wrap items-baseline gap-x-2">
                    <span className="font-medium">{dispatch.volunteer.name ?? "Volunteer"}</span>
                    {dispatch.volunteer.is_demo && (
                      <span className="text-[11px] text-sz-text-3">demo volunteer</span>
                    )}
                  </p>
                  <p className="font-mono text-[11px] text-sz-text-3">
                    {dispatch.volunteer.phone_masked} · offered {clock(dispatch.offered_at)}
                    {dispatch.arrived_at ? ` · arrived ${clock(dispatch.arrived_at)}` : ""}
                  </p>
                </div>
                <StatusPill tone={offerTone(dispatch.status)}>
                  {OFFER_LABEL[dispatch.status]}
                </StatusPill>
              </li>
            ))}
          </ul>
        )}
      </Section>

      <Section title="Send this out">
        <ChannelPicker value={channel} onChange={setChannel} disabled={busy || !canDispatch} />

        {officialFirst && (
          <p className="mt-3 flex gap-2 rounded-sm border border-sz-elev/40 bg-sz-elev/10 px-2.5 py-2 text-[12px] text-sz-elev">
            <Phone className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden="true" />
            <span>
              A {category} case is never volunteer-only. The official number went out in the
              first reply, and the handoff is created whichever channel you pick. A volunteer is
              an extra pair of hands.
            </span>
          </p>
        )}

        <div className="mt-3.5 flex flex-wrap gap-2">
          <button
            type="button"
            disabled={busy || !canDispatch}
            onClick={() => onApprove(channel)}
            className="inline-flex grow basis-40 cursor-pointer items-center justify-center gap-2 rounded-sm bg-sz-water px-3.5 py-2.5 font-semibold text-sz-on-fill transition-opacity hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-40"
          >
            {busy && <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden="true" />}
            {busy ? "Sending" : "Approve and send"}
          </button>
          <button
            type="button"
            disabled={busy}
            onClick={onReopen}
            className="rounded-sm border border-sz-line bg-sz-raised px-3.5 py-2.5 text-sz-text-2 transition-colors hover:text-sz-text disabled:opacity-40"
          >
            Re-open at top
          </button>
        </div>

        {!canDispatch && (
          <p className="mt-2.5 text-[12px] text-sz-text-3">
            Approving is disabled until there is a pin. Nothing useful can be sent without one.
          </p>
        )}
      </Section>

      <section className="px-4 py-4 sm:px-5">
        <h3 className="mb-2.5 font-medium">Responder handoff</h3>
        {link ? (
          <>
            <p className="flex items-center gap-2.5 rounded-sm border border-sz-line bg-sz-raised px-2.5 py-2">
              <Link2 className="h-3.5 w-3.5 shrink-0 text-sz-text-3" aria-hidden="true" />
              <span className="truncate font-mono text-[12px] text-sz-text-2">
                {BRAND_DOMAIN}/r/{link.token}
              </span>
            </p>
            <p className="mt-2 text-[12px] text-sz-text-3">
              {link.target_label ? `Prepared for ${link.target_label}. ` : ""}Read-only, no login,
              expires on its own. Sending it is a message from you, not an integration with any
              service.
            </p>
          </>
        ) : (
          <p className="text-[12px] text-sz-text-3">
            No handoff link yet. Approving on Responder link or Both creates one.
          </p>
        )}
      </section>
    </aside>
  );
}
