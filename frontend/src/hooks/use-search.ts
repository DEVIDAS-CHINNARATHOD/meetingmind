"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { useQuery } from "@tanstack/react-query";
import { searchService } from "@/services";
import type { SearchResponse } from "@/types";

interface UseSearchOptions {
  mode?: "text" | "semantic" | "hybrid";
  debounceMs?: number;
  minLength?: number;
}

export function useSearch({
  mode = "hybrid",
  debounceMs = 350,
  minLength = 2,
}: UseSearchOptions = {}) {
  const [query, setQuery] = useState("");
  const [debouncedQuery, setDebouncedQuery] = useState("");
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (timerRef.current) clearTimeout(timerRef.current);
    timerRef.current = setTimeout(() => {
      setDebouncedQuery(query);
    }, debounceMs);
    return () => { if (timerRef.current) clearTimeout(timerRef.current); };
  }, [query, debounceMs]);

  const enabled = debouncedQuery.length >= minLength;

  const { data, isLoading, isFetching } = useQuery<SearchResponse>({
    queryKey: ["search", debouncedQuery, mode],
    queryFn: () => searchService.search(debouncedQuery, mode),
    enabled,
    staleTime: 1000 * 30,
  });

  const clear = useCallback(() => {
    setQuery("");
    setDebouncedQuery("");
  }, []);

  return {
    query,
    setQuery,
    results: data?.results ?? [],
    resultCount: data?.count ?? 0,
    isLoading: isLoading && isFetching && enabled,
    hasQuery: enabled,
    clear,
  };
}
