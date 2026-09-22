"use client";

import type { EvaluationDetail } from "@/lib/types";
import { DecisionBadge } from "./DecisionBadge";

function ChoiceRow({
  label,
  choice,
}: {
  label: string;
  choice: { choice: string; confidence: number; probabilities: Record<string, number> };
}) {
  return (
    <div className="rounded-md border border-line bg-canvas p-3">
      <div className="flex items-start justify-between gap-3">
        <span className="min-w-0 text-sm text-muted">{label}</span>
        <span className="shrink-0 whitespace-nowrap font-mono text-xs text-faint">
          {choice.confidence.toFixed(2)} confidence
        </span>
      </div>
      <p className="mt-1 text-sm font-medium text-ink">{choice.choice}</p>
      <div className="mt-2 flex flex-wrap gap-2">
        {Object.entries(choice.probabilities).map(([option, p]) => (
          <span key={option} className="rounded bg-line/50 px-2 py-0.5 font-mono text-xs text-muted">
            {option} {(p * 100).toFixed(0)}%
          </span>
        ))}
      </div>
    </div>
  );
}

export function DecisionPanel({ evaluation, loading }: { evaluation: EvaluationDetail | null; loading: boolean }) {
  return (
    <section className="flex min-w-0 flex-col gap-5 bg-panel p-6">
      <header>
        <h2 className="text-base font-medium text-ink">Decision</h2>
        <p className="mt-1 text-sm text-muted">Hard rules run first; Jev's semantic check only runs if they pass.</p>
      </header>

      {loading && <p className="text-sm text-muted">Evaluating…</p>}

      {!loading && !evaluation && <p className="text-sm text-faint">Run a scenario to see Gatehouse's reasoning here.</p>}

      {!loading && evaluation && (
        <div className="flex flex-col gap-4">
          <div className="flex flex-wrap items-center gap-3">
            <DecisionBadge decision={evaluation.decision} />
            <span className="font-mono text-xs text-faint">
              {evaluation.gateway_latency_ms.toFixed(0)}ms gateway
              {evaluation.jev_latency_ms !== null && ` · ${evaluation.jev_latency_ms.toFixed(0)}ms jev`}
              {evaluation.jev_model_version && ` · ${evaluation.jev_model_version}`}
            </span>
          </div>

          <ul className="flex flex-col gap-1.5">
            {evaluation.reason_explanations.map((explanation, i) => (
              <li key={i} className="text-sm text-ink">
                <span className="mr-1.5 rounded bg-line/50 px-1.5 py-0.5 font-mono text-xs text-muted">
                  {evaluation.reason_codes[i]}
                </span>
                {explanation}
              </li>
            ))}
          </ul>

          <div>
            <h3 className="mb-2 text-sm text-muted">Hard rule check</h3>
            <div className="rounded-md border border-line bg-canvas p-3 text-sm">
              <span className={evaluation.hard_rule_result.ok ? "text-allow" : "text-block"}>
                {evaluation.hard_rule_result.ok ? "Passed" : "Failed"}
              </span>
              {evaluation.hard_rule_result.reason_codes.length > 0 && (
                <span className="ml-2 font-mono text-xs text-muted">
                  {evaluation.hard_rule_result.reason_codes.join(", ")}
                </span>
              )}
            </div>
          </div>

          {evaluation.jev_result && (
            <div>
              <h3 className="mb-2 text-sm text-muted">Jev answers</h3>
              <div className="flex flex-col gap-2">
                <ChoiceRow label="Does the action match the request?" choice={evaluation.jev_result.match} />
                <ChoiceRow label="Was this action explicitly requested?" choice={evaluation.jev_result.explicit} />
                <ChoiceRow label="Is the request specific enough?" choice={evaluation.jev_result.specific} />
              </div>
            </div>
          )}
        </div>
      )}
    </section>
  );
}
