import axios from "axios";

const TOKEN_KEY = "crm_access_token";

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string | null): void {
  if (token) {
    localStorage.setItem(TOKEN_KEY, token);
  } else {
    localStorage.removeItem(TOKEN_KEY);
  }
}

export const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || "/api/v1",
  timeout: 15000,
});

api.interceptors.request.use((config) => {
  const token = getToken();
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error?.response?.status === 401) {
      setToken(null);
      if (!window.location.pathname.startsWith("/login")) {
        window.location.assign("/login");
      }
    }
    return Promise.reject(error);
  },
);

export function getErrorMessage(error: unknown, fallback = "请求失败"): string {
  if (axios.isAxiosError(error)) {
    const data = error.response?.data as { message?: string; detail?: string } | undefined;
    return data?.message || data?.detail || error.message || fallback;
  }
  if (error instanceof Error) {
    return error.message;
  }
  return fallback;
}
