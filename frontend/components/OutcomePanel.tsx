"use client";

import type { EvaluationDetail } from "@/lib/types";

function Kv({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between gap-3 text-sm">
      <span className="shrink-0 text-muted">{label}</span>
      <span className="min-w-0 break-words text-right font-mono text-ink">{value}</span>
    </div>
  );
}

function centsToDollars(cents: unknown): string {
  return typeof cents === "number" ? `$${(cents / 100).toFixed(2)}` : String(cents);
}

export function OutcomePanel({
  evaluation,
  approving,
  executing,
  actionError,
  onApprove,
  onExecute,
}: {
  evaluation: EvaluationDetail | null;
  approving: boolean;
  executing: boolean;
  actionError: string | null;
  onApprove: () => void;
  onExecute: () => void;
}) {
  if (!evaluation) {
    return (
      <section className="flex min-w-0 flex-col gap-5 bg-panel p-6">
        <header>
          <h2 className="text-base font-medium text-ink">Outcome</h2>
        </header>
        <p className="text-sm text-faint">Order state, approvals, and execution history will show up here.</p>
      </section>
    );
  }

  const needsApproval = evaluation.decision === "REVIEW";
  const canApprove = needsApproval && !evaluation.approval;
  const approvalUsable =
    evaluation.approval &&
    evaluation.approval.status === "approved" &&
    new Date(evaluation.approval.expires_at) > new Date();
  const canExecute = (evaluation.decision === "ALLOW" || approvalUsable) && !evaluation.execution;
  const canRetry = !!evaluation.execution;

  const before = evaluation.hard_rule_result.data ?? {};
  const after = evaluation.execution?.result ?? null;

  return (
    <section className="flex min-w-0 flex-col gap-5 bg-panel p-6">
      <header>
        <h2 className="text-base font-medium text-ink">Outcome</h2>
        <p className="mt-1 text-sm text-muted">Nothing here is simulated — these are real backend state changes.</p>
      </header>

      <div className="rounded-md border border-line bg-canvas p-3">
        <h3 className="mb-2 text-sm text-muted">Order state</h3>
        <div className="flex flex-col gap-1">
          {"remaining_balance_cents_before" in before && (
            <Kv label="Balance before" value={centsToDollars(before.remaining_balance_cents_before)} />
          )}
          {after && "remaining_balance_cents" in after && (
            <Kv label="Balance after" value={centsToDollars(after.remaining_balance_cents)} />
          )}
          {"previous_address" in before && (
            <Kv label="Address before" value={JSON.stringify(before.previous_address)} />
          )}
          {after && "address" in after && <Kv label="Address after" value={JSON.stringify(after.address)} />}
          {"remaining_balance_cents" in before && (
            <Kv label="Remaining balance" value={centsToDollars(before.remaining_balance_cents)} />
          )}
          {"eligible" in before && <Kv label="Eligible" value={String(before.eligible)} />}
          {"shipment_state" in before && <Kv label="Shipment state" value={String(before.shipment_state)} />}
          {Object.keys(before).length === 0 && !after && (
            <p className="text-sm text-faint">No order data — the action was blocked before any read occurred.</p>
          )}
        </div>
      </div>

      <div className="flex flex-col gap-2">
        {canApprove && (
          <button
            onClick={onApprove}
            disabled={approving}
            className="rounded-md bg-ink px-4 py-2.5 text-sm font-medium text-canvas transition-opacity hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-40"
          >
            {approving ? "Approving…" : "Approve"}
          </button>
        )}
        {evaluation.approval && !approvalUsable && !evaluation.execution && (
          <p className="text-sm text-block">This approval has expired or was already used — re-approve to continue.</p>
        )}
        {(canExecute || canRetry) && (
          <button
            onClick={onExecute}
            disabled={executing}
            className="rounded-md border border-line px-4 py-2.5 text-sm font-medium text-ink transition-colors hover:border-faint disabled:cursor-not-allowed disabled:opacity-40"
          >
            {executing ? "Executing…" : canRetry ? "Retry (same request)" : "Execute"}
          </button>
        )}
        {actionError && <p className="text-sm text-block">{actionError}</p>}
      </div>

      {evaluation.execution && (
        <div className="min-w-0 rounded-md border border-line bg-canvas p-3">
          <div className="mb-2 flex items-center justify-between">
            <h3 className="text-sm text-muted">Execution</h3>
            {evaluation.execution.replayed && (
              <span className="rounded bg-line/50 px-2 py-0.5 text-xs text-muted">replayed — no new mutation</span>
            )}
          </div>
          <pre className="min-w-0 overflow-x-auto font-mono text-xs text-muted">
            {JSON.stringify(evaluation.execution.result, null, 2)}
          </pre>
        </div>
      )}
    </section>
  );
}
