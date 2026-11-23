import type { components } from "../generated/api";
export type Schema = components["schemas"];
export type Envelope<T> = { data: T; meta: Schema["Meta"]; warnings: string[] };
export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}
export async function api<T>(
  path: string,
  init: RequestInit = {},
): Promise<Envelope<T>> {
  const response = await fetch(`/api/v1${path}`, {
    ...init,
    credentials: "same-origin",
    headers: { "Content-Type": "application/json", ...init.headers },
    cache: "no-store",
  });
  if (!response.ok) {
    const issue = await response
      .json()
      .catch(() => ({ detail: "서버 응답을 확인할 수 없습니다." }));
    if (
      response.status === 401 &&
      !path.startsWith("/auth/login") &&
      typeof window !== "undefined"
    )
      window.location.replace(new URL("/login/", window.location.origin));
    throw new ApiError(
      response.status,
      issue.detail ?? "요청을 처리하지 못했습니다.",
    );
  }
  return response.json();
}
export function post<T>(path: string, body: unknown) {
  return api<T>(path, { method: "POST", body: JSON.stringify(body) });
}
export const money = (v: number | null | undefined, currency = "USD") =>
  v == null
    ? "—"
    : new Intl.NumberFormat("ko-KR", {
        maximumFractionDigits: currency === "KRW" ? 0 : 2,
      }).format(v);
export const pct = (v: number | null | undefined) =>
  v == null ? "—" : `${v >= 0 ? "▲" : "▼"} ${Math.abs(v).toFixed(2)}%`;
