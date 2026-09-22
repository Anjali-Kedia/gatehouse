export type Decision = "ALLOW" | "BLOCK" | "CLARIFY" | "REVIEW";

export type ToolName =
  | "get_order"
  | "check_refund_eligibility"
  | "issue_refund"
  | "change_delivery_address";

export interface ProposedAction {
  tool: ToolName;
  arguments: Record<string, unknown>;
}

export interface ChoiceAnswer {
  choice: string;
  confidence: number;
  probabilities: Record<string, number>;
}

export interface JevResult {
  match: ChoiceAnswer;
  explicit: ChoiceAnswer;
  specific: ChoiceAnswer;
  model: string;
  latency_ms: number;
}

export interface HardRuleResult {
  ok: boolean;
  reason_codes: string[];
  data: Record<string, unknown> | null;
}

export interface Evaluation {
  id: string;
  decision: Decision;
  reason_codes: string[];
  reason_explanations: string[];
  user_request: string;
  proposed_tool: ToolName;
  proposed_arguments: Record<string, unknown>;
  hard_rule_result: HardRuleResult;
  jev_result: JevResult | null;
  gateway_latency_ms: number;
  jev_latency_ms: number | null;
  jev_model_version: string | null;
  action_hash: string;
  created_at: string;
}

export interface Approval {
  id: string;
  evaluation_id: string;
  status: "approved" | "consumed" | "expired";
  expires_at: string;
  created_at: string;
  consumed_at: string | null;
}

export interface ExecutionResult {
  id: string;
  evaluation_id: string;
  status: "success";
  result: Record<string, unknown>;
  replayed: boolean;
  created_at: string;
}

export interface EvaluationDetail extends Evaluation {
  approval: Approval | null;
  execution: ExecutionResult | null;
}

export interface ApiErrorBody {
  detail:
    | string
    | {
        reason_codes: string[];
        reason_explanations: string[];
      };
}
