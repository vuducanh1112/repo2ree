import type { ApiErrorEnvelope } from "./apiTypes";

interface ApiClientOptions {
  baseUrl?: string;
  headers?: Record<string, string>;
}

class ApiRequestError extends Error {
  status: number;
  code: string;
  /**
   * Whether the caller may safely retry. Sourced from the error envelope so UI
   * policy can distinguish a transient outage from a conflict or a permanent
   * validation failure instead of treating every error the same.
   */
  retryable: boolean;
  details?: ApiErrorEnvelope["error"]["details"];

  constructor(
    status: number,
    code: string,
    message: string,
    retryable: boolean,
    details?: ApiErrorEnvelope["error"]["details"],
  ) {
    super(message);
    this.name = "ApiRequestError";
    this.status = status;
    this.code = code;
    this.retryable = retryable;
    this.details = details;
  }
}

export class ApiClient {
  private baseUrl: string;
  private headers: Record<string, string>;

  constructor(options: ApiClientOptions = {}) {
    this.baseUrl = options.baseUrl || "";
    this.headers = options.headers || {};
  }

  async request<TResponse>(
    path: string,
    init: RequestInit = {},
    searchParams?: URLSearchParams,
  ): Promise<TResponse> {
    const url = this.buildUrl(path, searchParams);
    const headers: Record<string, string> = {
      ...this.headers,
      ...(init.headers as Record<string, string> | undefined),
    };

    if (init.body && !headers["Content-Type"]) {
      headers["Content-Type"] = "application/json";
    }

    const response = await fetch(url, {
      ...init,
      headers,
    });

    const isJson = response.headers.get("content-type")?.includes("application/json");
    const payload = isJson ? await response.json() : null;

    if (!response.ok) {
      const errorPayload = payload as ApiErrorEnvelope | null;
      throw new ApiRequestError(
        response.status,
        errorPayload?.error.code || "request_failed",
        errorPayload?.error.message || response.statusText,
        errorPayload?.error.retryable ?? false,
        errorPayload?.error.details,
      );
    }

    return payload as TResponse;
  }

  async requestArrayBuffer(
    path: string,
    init: RequestInit = {},
    searchParams?: URLSearchParams,
  ): Promise<ArrayBuffer> {
    const result = await this.requestArrayBufferWithMeta(path, init, searchParams);
    return result.bytes;
  }

  async requestArrayBufferWithMeta(
    path: string,
    init: RequestInit = {},
    searchParams?: URLSearchParams,
  ): Promise<{ bytes: ArrayBuffer; headers: Headers }> {
    const url = this.buildUrl(path, searchParams);
    const headers: Record<string, string> = {
      ...this.headers,
      ...(init.headers as Record<string, string> | undefined),
    };

    const response = await fetch(url, {
      ...init,
      headers,
    });

    if (!response.ok) {
      const isJson = response.headers.get("content-type")?.includes("application/json");
      const payload = isJson ? ((await response.json()) as ApiErrorEnvelope) : null;
      throw new ApiRequestError(
        response.status,
        payload?.error.code || "request_failed",
        payload?.error.message || response.statusText,
        payload?.error.retryable ?? false,
        payload?.error.details,
      );
    }

    return { bytes: await response.arrayBuffer(), headers: response.headers };
  }

  private buildUrl(path: string, searchParams?: URLSearchParams): string {
    const normalizedPath = path.startsWith("/") ? path : `/${path}`;
    const url = `${this.baseUrl}${normalizedPath}`;
    if (!searchParams || Array.from(searchParams.keys()).length === 0) {
      return url;
    }
    return `${url}?${searchParams.toString()}`;
  }
}
