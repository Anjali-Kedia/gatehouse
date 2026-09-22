"use client";

import { useEffect, useMemo, useState } from "react";
import { ScenarioPanel } from "@/components/ScenarioPanel";
import { DecisionPanel } from "@/components/DecisionPanel";
import { OutcomePanel } from "@/components/OutcomePanel";
import { EvaluationHistoryTable } from "@/components/EvaluationHistoryTable";
import { GateMark } from "@/components/GateMark";
import { approveEvaluation, createEvaluation, executeEvaluation, getEvaluation, listEvaluations, GatehouseApiError } from "@/lib/api";
import { SCENARIOS } from "@/lib/scenarios";
import type { EvaluationDetail, Evaluation, ToolName } from "@/lib/types";

const DEFAULT_SCENARIO = SCENARIOS[0]!;

export default function Home() {
  const [scenarioId, setScenarioId] = useState(DEFAULT_SCENARIO.id);
  const [userRequest, setUserRequest] = useState(DEFAULT_SCENARIO.userRequest);
  const [tool, setTool] = useState<ToolName>(DEFAULT_SCENARIO.proposedAction.tool);
  const [argumentsText, setArgumentsText] = useState(JSON.stringify(DEFAULT_SCENARIO.proposedAction.arguments, null, 2));

  const [evaluation, setEvaluation] = useState<EvaluationDetail | null>(null);
  const [history, setHistory] = useState<Evaluation[]>([]);
  const [running, setRunning] = useState(false);
  const [approving, setApproving] = useState(false);
  const [executing, setExecuting] = useState(false);
  const [runError, setRunError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  const argumentsError = useMemo(() => {
    try {
      JSON.parse(argumentsText);
      return null;
    } catch {
      return "Arguments must be valid JSON.";
    }
  }, [argumentsText]);

  const refreshHistory = async () => {
    try {
      setHistory(await listEvaluations());
    } catch {
      // History is a convenience panel — a failed refresh shouldn't block the demo.
    }
  };

  useEffect(() => {
    // setHistory runs after the await inside refreshHistory, not synchronously
    // during this callback, so this isn't the cascading-render pattern the
    // rule is guarding against — it's the standard fetch-on-mount shape.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void refreshHistory();
  }, []);

  function applyScenario(id: string) {
    setScenarioId(id);
    const scenario = SCENARIOS.find((s) => s.id === id);
    if (scenario) {
      setUserRequest(scenario.userRequest);
      setTool(scenario.proposedAction.tool);
      setArgumentsText(JSON.stringify(scenario.proposedAction.arguments, null, 2));
    }
  }

  async function handleRun() {
    setRunning(true);
    setRunError(null);
    setActionError(null);
    setEvaluation(null);
    try {
      const created = await createEvaluation(userRequest, { tool, arguments: JSON.parse(argumentsText) });
      const detail = await getEvaluation(created.id);
      setEvaluation(detail);
      await refreshHistory();
    } catch (err) {
      setRunError(err instanceof GatehouseApiError ? err.message : "Failed to reach Gatehouse.");
    } finally {
      setRunning(false);
    }
  }

  async function handleSelectHistoryEntry(id: string) {
    setActionError(null);
    try {
      setEvaluation(await getEvaluation(id));
    } catch (err) {
      setRunError(err instanceof GatehouseApiError ? err.message : "Failed to load evaluation.");
    }
  }

  async function handleApprove() {
    if (!evaluation) return;
    setApproving(true);
    setActionError(null);
    try {
      await approveEvaluation(evaluation.id);
      setEvaluation(await getEvaluation(evaluation.id));
    } catch (err) {
      setActionError(err instanceof GatehouseApiError ? err.message : "Approval failed.");
    } finally {
      setApproving(false);
    }
  }

  async function handleExecute() {
    if (!evaluation) return;
    setExecuting(true);
    setActionError(null);
    try {
      // Use this call's own response for `replayed` — a GET afterwards has no
      // way to know whether *this particular* execute call was the original
      // mutation or a duplicate-key replay, only the execute response does.
      const executionResult = await executeEvaluation(evaluation.id);
      const detail = await getEvaluation(evaluation.id);
      setEvaluation({ ...detail, execution: executionResult });
      await refreshHistory();
    } catch (err) {
      setActionError(err instanceof GatehouseApiError ? err.message : "Execution failed.");
    } finally {
      setExecuting(false);
    }
  }

  return (
    <main className="mx-auto flex max-w-7xl flex-col gap-8 px-6 py-12">
      <header className="flex items-start gap-3">
        <GateMark className="mt-1 h-6 w-6 shrink-0 text-ink" />
        <div className="flex flex-col gap-1">
          <h1 className="text-lg font-semibold text-ink">Gatehouse</h1>
          <p className="max-w-xl text-sm text-muted">
            Check intent. Enforce rules. Execute safely. A Jev-powered gateway that checks an AI agent&rsquo;s
            proposed actions before executing them.
          </p>
        </div>
      </header>

      {runError && (
        <div className="rounded-md border border-block/40 bg-block/10 px-4 py-3 text-sm text-block">{runError}</div>
      )}

      <div className="grid grid-cols-1 divide-y divide-line overflow-hidden rounded-lg border border-line lg:grid-cols-3 lg:divide-x lg:divide-y-0">
        <ScenarioPanel
          scenarioId={scenarioId}
          userRequest={userRequest}
          tool={tool}
          argumentsText={argumentsText}
          argumentsError={argumentsError}
          running={running}
          onSelectScenario={applyScenario}
          onUserRequestChange={(v) => {
            setUserRequest(v);
            setScenarioId("custom");
          }}
          onToolChange={(t) => {
            setTool(t);
            setScenarioId("custom");
          }}
          onArgumentsChange={(v) => {
            setArgumentsText(v);
            setScenarioId("custom");
          }}
          onRun={handleRun}
        />
        <DecisionPanel evaluation={evaluation} loading={running} />
        <OutcomePanel
          evaluation={evaluation}
          approving={approving}
          executing={executing}
          actionError={actionError}
          onApprove={handleApprove}
          onExecute={handleExecute}
        />
      </div>

      <EvaluationHistoryTable evaluations={history} selectedId={evaluation?.id ?? null} onSelect={handleSelectHistoryEntry} />
    </main>
  );
}
