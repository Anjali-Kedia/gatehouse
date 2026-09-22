"use client";

import type { Evaluation } from "@/lib/types";
import { DecisionBadge } from "./DecisionBadge";

export function EvaluationHistoryTable({
  evaluations,
  selectedId,
  onSelect,
}: {
  evaluations: Evaluation[];
  selectedId: string | null;
  onSelect: (id: string) => void;
}) {
  return (
    <section className="rounded-lg border border-line bg-panel p-6">
      <h2 className="mb-4 text-base font-medium text-ink">Evaluation history</h2>
      {evaluations.length === 0 ? (
        <p className="text-sm text-faint">No evaluations yet in this sandbox session.</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b border-line text-sm text-muted">
                <th className="py-2 pr-4 font-normal">When</th>
                <th className="py-2 pr-4 font-normal">Tool</th>
                <th className="py-2 pr-4 font-normal">Decision</th>
                <th className="py-2 pr-4 font-normal">Reasons</th>
                <th className="py-2 pr-4 font-normal">Latency</th>
              </tr>
            </thead>
            <tbody>
              {evaluations.map((e) => (
                <tr
                  key={e.id}
                  onClick={() => onSelect(e.id)}
                  className={`cursor-pointer border-b border-line/60 transition-colors hover:bg-canvas ${
                    selectedId === e.id ? "bg-canvas" : ""
                  }`}
                >
                  <td className="py-2.5 pr-4 text-muted">{new Date(e.created_at).toLocaleTimeString()}</td>
                  <td className="py-2.5 pr-4 font-mono text-xs text-ink">{e.proposed_tool}</td>
                  <td className="py-2.5 pr-4">
                    <DecisionBadge decision={e.decision} />
                  </td>
                  <td className="py-2.5 pr-4 font-mono text-xs text-muted">{e.reason_codes.join(", ")}</td>
                  <td className="py-2.5 pr-4 font-mono text-xs text-muted">{e.gateway_latency_ms.toFixed(0)}ms</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
