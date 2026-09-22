import type { ApiErrorBody, Evaluation, EvaluationDetail, ProposedAction, Approval, ExecutionResult } from "./types";

// Must share a hostname with the page origin (both "localhost"), not just
// resolve to the same machine: SameSite=Lax cookies (our session cookie) are
// dropped on cross-site fetches, and "localhost" vs "127.0.0.1" count as
// different sites even though they're the same box.
const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export class GatehouseApiError extends Error {
  status: number;
  reasonCodes: string[];
  reasonExplanations: string[];

  constructor(status: number, body: ApiErrorBody) {
    const detail = body.detail;
    const isStructured = typeof detail === "object" && detail !== null;
    super(isStructured ? detail.reason_explanations.join(" ") : String(detail));
    this.status = status;
    this.reasonCodes = isStructured ? detail.reason_codes : [];
    this.reasonExplanations = isStructured ? detail.reason_explanations : [String(detail)];
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    credentials: "include", // carries the gatehouse_session cookie
    headers: { "Content-Type": "application/json", ...init?.headers },
  });
  if (!response.ok) {
    const body = (await response.json().catch(() => ({ detail: response.statusText }))) as ApiErrorBody;
    throw new GatehouseApiError(response.status, body);
  }
  return response.json() as Promise<T>;
}

export function createEvaluation(userRequest: string, proposedAction: ProposedAction): Promise<Evaluation> {
  return request<Evaluation>("/evaluations", {
    method: "POST",
    body: JSON.stringify({ user_request: userRequest, proposed_action: proposedAction }),
  });
}

export function listEvaluations(): Promise<Evaluation[]> {
  return request<Evaluation[]>("/evaluations");
}

export function getEvaluation(id: string): Promise<EvaluationDetail> {
  return request<EvaluationDetail>(`/evaluations/${id}`);
}

export function approveEvaluation(id: string): Promise<Approval> {
  return request<Approval>(`/evaluations/${id}/approve`, { method: "POST" });
}

export function executeEvaluation(id: string, idempotencyKey?: string): Promise<ExecutionResult> {
  return request<ExecutionResult>(`/evaluations/${id}/execute`, {
    method: "POST",
    body: JSON.stringify(idempotencyKey ? { idempotency_key: idempotencyKey } : {}),
  });
}
