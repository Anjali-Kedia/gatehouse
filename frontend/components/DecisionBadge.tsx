import type { Decision } from "@/lib/types";

const STYLES: Record<Decision, string> = {
  ALLOW: "bg-allow/15 text-allow border-allow/40",
  BLOCK: "bg-block/15 text-block border-block/40",
  CLARIFY: "bg-clarify/15 text-clarify border-clarify/40",
  REVIEW: "bg-review/15 text-review border-review/40",
};

export function DecisionBadge({ decision }: { decision: Decision }) {
  return (
    <span className={`inline-flex items-center rounded border px-2.5 py-1 text-sm font-medium ${STYLES[decision]}`}>
      {decision}
    </span>
  );
}
