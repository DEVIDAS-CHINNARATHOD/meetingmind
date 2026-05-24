import axios, { AxiosError, AxiosInstance, AxiosRequestConfig } from "axios";
import { toast } from "sonner";

const BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

// ── Client factory ────────────────────────────────────────────

function createApiClient(): AxiosInstance {
  const client = axios.create({
    baseURL: `${BASE_URL}/api`,
    timeout: 60_000,
    headers: { "Content-Type": "application/json" },
  });

  // ── Request interceptor: attach JWT ───────────────────────
  client.interceptors.request.use(
    (config) => {
      if (typeof window !== "undefined") {
        const token = localStorage.getItem("mm_access_token");
        if (token) {
          config.headers.Authorization = `Bearer ${token}`;
        }
      }
      return config;
    },
    (error) => Promise.reject(error)
  );

  // ── Response interceptor: handle 401, show toasts ─────────
  client.interceptors.response.use(
    (response) => response,
    async (error: AxiosError) => {
      const status = error.response?.status;

      if (status === 401) {
        // Try token refresh
        const refreshed = await attemptTokenRefresh();
        if (refreshed && error.config) {
          const token = localStorage.getItem("mm_access_token");
          error.config.headers = error.config.headers ?? {};
          error.config.headers.Authorization = `Bearer ${token}`;
          return client.request(error.config);
        }
        // Refresh failed → redirect to login
        if (typeof window !== "undefined") {
          localStorage.removeItem("mm_access_token");
          localStorage.removeItem("mm_refresh_token");
          window.location.href = "/auth/login";
        }
      } else if (status === 429) {
        toast.error("Too many requests. Please slow down.");
      } else if (status === 413) {
        toast.error("File is too large. Maximum upload size is 2 GB.");
      } else if (status && status >= 500) {
        const detail = (error.response?.data as { detail?: string })?.detail;
        toast.error(detail ?? "Server error. Please try again.");
      }

      return Promise.reject(error);
    }
  );

  return client;
}

async function attemptTokenRefresh(): Promise<boolean> {
  try {
    const refresh = localStorage.getItem("mm_refresh_token");
    if (!refresh) return false;

    const res = await axios.post(`${BASE_URL}/api/auth/refresh`, {
      refresh_token: refresh,
    });
    const { access_token, refresh_token } = res.data;
    localStorage.setItem("mm_access_token", access_token);
    localStorage.setItem("mm_refresh_token", refresh_token);
    return true;
  } catch {
    return false;
  }
}

export const api = createApiClient();

// ── Auth helpers ──────────────────────────────────────────────

export function setTokens(accessToken: string, refreshToken: string) {
  if (typeof window !== "undefined") {
    localStorage.setItem("mm_access_token", accessToken);
    localStorage.setItem("mm_refresh_token", refreshToken);
  }
}

export function clearTokens() {
  if (typeof window !== "undefined") {
    localStorage.removeItem("mm_access_token");
    localStorage.removeItem("mm_refresh_token");
  }
}

// ── Typed helpers ─────────────────────────────────────────────

export async function get<T>(url: string, config?: AxiosRequestConfig): Promise<T> {
  const res = await api.get<T>(url, config);
  return res.data;
}

export async function post<T>(url: string, data?: unknown, config?: AxiosRequestConfig): Promise<T> {
  const res = await api.post<T>(url, data, config);
  return res.data;
}

export async function patch<T>(url: string, data?: unknown): Promise<T> {
  const res = await api.patch<T>(url, data);
  return res.data;
}

export async function del(url: string): Promise<void> {
  await api.delete(url);
}

// ── Error extractor ───────────────────────────────────────────

export function getErrorMessage(error: unknown): string {
  if (axios.isAxiosError(error)) {
    const detail = (error.response?.data as { detail?: string })?.detail;
    return detail ?? error.message ?? "An error occurred";
  }
  if (error instanceof Error) return error.message;
  return "An unexpected error occurred";
}
