import { useMemo } from "react";
import { Navigate } from "react-router";

import { AppShell } from "../components/AppShell";
import { CommandMap } from "../components/map/CommandMap";
import { DistressFeed } from "../components/feed/DistressFeed";
import { EventTimeline } from "../components/timeline/EventTimeline";
import { ResponsePanel } from "../components/dispatch/ResponsePanel";
import { TriageAssistant } from "../components/triage/TriageAssistant";
import { useDashboard } from "../hooks/useDashboard";
import { severityOf } from "../lib/severity";

export default function Dashboard() {
  const {
    cases,
    volunteers,
    admin,
    source,
    error,
    unauthorized,
    streaming,
    loading,
    selectedId,
    selected,
    select,
    approve,
    reopen,
    toggleKillSwitch,
    reload,
    busyCaseId,
  } = useDashboard();

  const open = useMemo(
    () => cases.filter((row) => row.status !== "resolved" && row.status !== "rejected"),
    [cases],
  );

  const critical = useMemo(
    () => open.filter((row) => severityOf(row.priority_score) === "critical"),
    [open],
  );

  /** One sentence for the banner: how many, where, and how many have not left
   *  the queue yet. Written as prose rather than a string of counts, because
   *  it is read at a glance by someone deciding what to do next. */
  const alert = useMemo(() => {
    if (critical.length === 0) return null;

    const byZone = new Map<string, number>();
    critical.forEach((row) => {
      const name = row.zone?.name;
      if (name) byZone.set(name, (byZone.get(name) ?? 0) + 1);
    });
    const worst = [...byZone.entries()].sort((a, b) => b[1] - a[1])[0];
    const waiting = critical.filter((row) => row.dispatch_status === "none").length;

    let text = `${critical.length} critical ${critical.length === 1 ? "case" : "cases"} open`;
    if (worst && worst[1] > 1) text += `, ${worst[1]} of them in ${worst[0]}`;
    text += ".";
    if (waiting > 0) {
      text += ` ${waiting} ${waiting === 1 ? "has" : "have"} not been sent out yet.`;
    }
    return text;
  }, [critical]);

  // A session that ends while the page is open sends them back to sign in
  // rather than leaving a shell full of 401s on screen.
  if (unauthorized) return <Navigate to="/login" replace />;

  return (
    <AppShell
      admin={admin}
      source={source}
      streaming={streaming}
      openCount={open.length}
      criticalCount={critical.length}
      onToggleKillSwitch={toggleKillSwitch}
      alert={alert}
      error={source === "error" ? error : null}
      onRetry={reload}
      fill
    >
      {/* Wraps into a single stacked column on a phone. From `lg` it must NOT
          wrap: a wrapping flex container sizes each line to its content, so the
          columns would ignore the shell height, stop scrolling internally and
          push the timeline off the bottom of the screen. */}
      <div className="flex min-h-0 grow flex-wrap items-stretch lg:flex-nowrap">
        <div className="flex min-h-0 w-full shrink-0 grow basis-80 flex-col lg:w-auto lg:max-w-sm">
          <TriageAssistant cases={cases} />
          <DistressFeed
            cases={cases}
            selectedId={selectedId}
            busyCaseId={busyCaseId}
            onSelect={select}
            onDispatch={(id) => approve(id, "volunteers")}
            loading={loading}
          />
        </div>

        <div className="flex min-h-0 w-full min-w-0 grow-[999] basis-[28rem] flex-col gap-3 p-3 lg:w-auto">
          <div className="sz-card flex min-h-0 grow flex-col overflow-hidden">
            <CommandMap
              cases={cases}
              volunteers={volunteers}
              selectedId={selectedId}
              onSelect={select}
            />
          </div>
          {selected && (
            <div className="sz-card shrink-0 overflow-hidden">
              <EventTimeline key={selected.id} events={selected.events} caseId={selected.id} />
            </div>
          )}
        </div>

        <ResponsePanel
          key={selected?.id ?? "none"}
          row={selected}
          busy={busyCaseId !== null && busyCaseId === selected?.id}
          onApprove={(channel) => selected && approve(selected.id, channel)}
          onReopen={() => selected && reopen(selected.id)}
        />
      </div>
    </AppShell>
  );
}
