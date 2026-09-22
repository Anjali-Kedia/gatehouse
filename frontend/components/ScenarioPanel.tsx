"use client";

import type { ToolName } from "@/lib/types";
import { SCENARIOS } from "@/lib/scenarios";
import { Select } from "./Select";

const TOOLS: ToolName[] = ["get_order", "check_refund_eligibility", "issue_refund", "change_delivery_address"];

interface Props {
  scenarioId: string;
  userRequest: string;
  tool: ToolName;
  argumentsText: string;
  argumentsError: string | null;
  running: boolean;
  onSelectScenario: (id: string) => void;
  onUserRequestChange: (value: string) => void;
  onToolChange: (tool: ToolName) => void;
  onArgumentsChange: (value: string) => void;
  onRun: () => void;
}

export function ScenarioPanel({
  scenarioId,
  userRequest,
  tool,
  argumentsText,
  argumentsError,
  running,
  onSelectScenario,
  onUserRequestChange,
  onToolChange,
  onArgumentsChange,
  onRun,
}: Props) {
  const selectedScenario = SCENARIOS.find((s) => s.id === scenarioId);

  return (
    <section className="flex min-w-0 flex-col gap-5 bg-panel p-6">
      <header>
        <h2 className="text-base font-medium text-ink">Scenario</h2>
        <p className="mt-1 text-sm text-muted">
          Simulated agent proposal. Edit the request or arguments to create a mistake.
        </p>
      </header>

      <div className="flex flex-col gap-1.5">
        <label className="text-sm text-muted">Demo scenario</label>
        <Select
          ariaLabel="Demo scenario"
          value={scenarioId}
          onValueChange={onSelectScenario}
          options={[{ value: "custom", label: "Custom" }, ...SCENARIOS.map((s) => ({ value: s.id, label: s.title }))]}
        />
        {selectedScenario && <p className="text-sm text-muted">{selectedScenario.expected}</p>}
      </div>

      <div className="flex flex-col gap-1.5">
        <label className="text-sm text-muted">User request</label>
        <textarea
          className="min-h-[72px] resize-none rounded-md border border-line bg-canvas px-3 py-2 text-sm text-ink placeholder:text-faint focus:border-ink focus:outline-none"
          value={userRequest}
          onChange={(e) => onUserRequestChange(e.target.value)}
        />
      </div>

      <div className="flex flex-col gap-1.5">
        <label className="text-sm text-muted">Proposed tool</label>
        <Select
          ariaLabel="Proposed tool"
          value={tool}
          onValueChange={(v) => onToolChange(v as ToolName)}
          options={TOOLS.map((t) => ({ value: t, label: t }))}
        />
      </div>

      <div className="flex flex-col gap-1.5">
        <label className="text-sm text-muted">Arguments (JSON)</label>
        <textarea
          spellCheck={false}
          className={`min-h-[110px] resize-none rounded-md border bg-canvas px-3 py-2 font-mono text-[13px] text-ink focus:outline-none ${
            argumentsError ? "border-block" : "border-line focus:border-ink"
          }`}
          value={argumentsText}
          onChange={(e) => onArgumentsChange(e.target.value)}
        />
        {argumentsError && <p className="text-sm text-block">{argumentsError}</p>}
      </div>

      <button
        onClick={onRun}
        disabled={running || !!argumentsError}
        className="mt-1 rounded-md bg-ink px-4 py-2.5 text-sm font-medium text-canvas transition-opacity hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-40"
      >
        {running ? "Evaluating…" : "Run through Gatehouse"}
      </button>
    </section>
  );
}
