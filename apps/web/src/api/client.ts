import type { RankingFilters, RankingResponse, ValuationDetail } from "./types";

const API_BASE = import.meta.env.VITE_API_BASE ?? "";

class ApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
  ) {
    super(message);
  }
}

async function request<T>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: { Accept: "application/json" },
  });
  if (!response.ok) {
    let message = `请求失败（${response.status}）`;
    try {
      const payload = (await response.json()) as { detail?: { message?: string } | string };
      if (typeof payload.detail === "string") {
        message = payload.detail;
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
  if (filters.staleOnly) query.set("stale_only", "true");
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
