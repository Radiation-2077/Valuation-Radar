import type {
  ClearJobsResult,
  Job,
  JobDebug,
  JobList,
  Instrument,
  InstrumentCreatePayload,
  InstrumentCreateResult,
  InstrumentLifecycleResult,
  InstrumentList,
  InstrumentPurgeResult,
  RankingFilters,
  RankingResponse,
  ReviewDecision,
  ReviewList,
  Schedule,
  SchedulePatch,
  ValuationDetail,
} from "./types";

const API_BASE = import.meta.env.VITE_API_BASE ?? "";

class ApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
  ) {
    super(message);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      Accept: "application/json",
      ...init?.headers,
    },
  });
  if (!response.ok) {
    let message = `请求失败（${response.status}）`;
    try {
      const payload = (await response.json()) as {
        detail?:
          | string
          | { message?: string }
          | Array<{ msg?: string; loc?: unknown[] }>;
      };
      if (typeof payload.detail === "string") {
        message = payload.detail;
      } else if (Array.isArray(payload.detail)) {
        message = payload.detail
          .map((item) => item.msg ?? "")
          .filter(Boolean)
          .join("；") || message;
      } else if (payload.detail?.message) {
        message = payload.detail.message;
      }
    } catch {
      // Keep the status-based fallback when the response is not JSON.
    }
    throw new ApiError(message, response.status);
  }
  return (await response.json()) as T;
}

export async function fetchRanking(filters: RankingFilters): Promise<RankingResponse> {
  const query = new URLSearchParams({ profile: filters.profile });
  if (filters.market) query.set("market", filters.market);
  if (filters.path) query.set("path", filters.path);
  if (filters.industry) query.set("industry", filters.industry);
  return request<RankingResponse>(`/api/v1/rankings?${query.toString()}`);
}

export async function fetchValuation(
  valuationMarketId: number,
  profile: string,
): Promise<ValuationDetail> {
  return request<ValuationDetail>(
    `/api/v1/valuations/${valuationMarketId}?profile=${encodeURIComponent(profile)}`,
  );
}

export async function fetchSchedule(): Promise<Schedule> {
  return request<Schedule>("/api/v1/schedule");
}

export async function updateSchedule(payload: SchedulePatch): Promise<Schedule> {
  return request<Schedule>("/api/v1/schedule", {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function fetchJobs(): Promise<JobList> {
  return request<JobList>("/api/v1/jobs?limit=20");
}

export async function fetchJobDebug(jobId: number): Promise<JobDebug> {
  return request<JobDebug>(`/api/v1/jobs/${jobId}/debug`);
}

export async function clearJobs(): Promise<ClearJobsResult> {
  return request<ClearJobsResult>("/api/v1/jobs", {
    method: "DELETE",
  });
}

function idempotencyKey(prefix: string): string {
  if (typeof globalThis.crypto?.randomUUID === "function") {
    return `${prefix}-${globalThis.crypto.randomUUID()}`;
  }
  return `${prefix}-${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

export async function createRefreshJob(): Promise<Job> {
  return request<Job>("/api/v1/jobs", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "Idempotency-Key": idempotencyKey("manual"),
    },
    body: JSON.stringify({ job_type: "market_refresh", scope: "all" }),
  });
}

export async function requestRevaluation(instrumentId: number): Promise<Job> {
  return request<Job>(`/api/v1/instruments/${instrumentId}/revaluations`, {
    method: "POST",
    headers: { "Idempotency-Key": idempotencyKey("revaluation") },
  });
}

export async function createInstrument(
  payload: InstrumentCreatePayload,
): Promise<InstrumentCreateResult> {
  return request<InstrumentCreateResult>("/api/v1/instruments", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function fetchInstruments(): Promise<InstrumentList> {
  return request<InstrumentList>("/api/v1/instruments");
}

export async function archiveInstrument(
  instrumentId: number,
): Promise<InstrumentLifecycleResult> {
  return request<InstrumentLifecycleResult>(`/api/v1/instruments/${instrumentId}`, {
    method: "DELETE",
  });
}

export async function restoreInstrument(
  instrumentId: number,
): Promise<InstrumentLifecycleResult> {
  return request<InstrumentLifecycleResult>(
    `/api/v1/instruments/${instrumentId}/restore`,
    { method: "POST" },
  );
}

export async function purgeInstrument(
  instrument: Pick<Instrument, "id" | "name">,
): Promise<InstrumentPurgeResult> {
  const query = new URLSearchParams({ confirmation: instrument.name });
  return request<InstrumentPurgeResult>(
    `/api/v1/instruments/${instrument.id}/purge?${query.toString()}`,
    { method: "DELETE" },
  );
}

export async function fetchReviews(): Promise<ReviewList> {
  return request<ReviewList>("/api/v1/reviews");
}

export async function decideReview(
  reportId: number,
  decision: "approve" | "reject",
): Promise<ReviewDecision> {
  return request<ReviewDecision>(`/api/v1/reviews/${reportId}/${decision}`, {
    method: "POST",
  });
}
