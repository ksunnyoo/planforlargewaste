import { keepPreviousData, useMutation, useQuery } from "@tanstack/react-query";
import { api, ApiError } from "./client";
import type { Estimate, EstimateRequest, Municipality, SearchItem } from "./types";

export function useMunicipalities() {
  return useQuery<Municipality[], ApiError>({
    queryKey: ["municipalities"],
    queryFn: async () => (await api.get<{ items: Municipality[] }>("/api/v1/municipalities")).data.items,
    staleTime: Infinity,
  });
}

export function useItemSearch(code: string | null, q: string) {
  return useQuery<SearchItem[], ApiError>({
    queryKey: ["items", code, q],
    enabled: !!code && q.trim().length > 0,
    placeholderData: keepPreviousData,
    queryFn: async () =>
      (await api.get<{ items: SearchItem[] }>("/api/v1/items/search", {
        params: { municipality_code: code, q: q.trim(), limit: 10 },
      })).data.items,
  });
}

export function useCreateEstimate() {
  return useMutation<Estimate, ApiError, EstimateRequest>({
    mutationFn: async (body) => (await api.post<Estimate>("/api/v1/estimates", body)).data,
  });
}

export function useEstimate(publicId: string | undefined) {
  return useQuery<Estimate, ApiError>({
    queryKey: ["estimate", publicId],
    enabled: !!publicId,
    retry: false,
    queryFn: async () => (await api.get<Estimate>(`/api/v1/estimates/${encodeURIComponent(publicId ?? "")}`)).data,
  });
}
