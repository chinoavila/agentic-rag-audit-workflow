// Cliente HTTP delgado contra el backend FastAPI. Siempre rutas relativas (`/api/...`): en dev
// Vite las proxea a BACKEND_URL (ver vite.config.ts), en producción nginx hace lo mismo
// (Dockerfile.frontend, tarea 6 del plan) -- así el bundle nunca hornea una URL de backend.
//
// Todavía sin uso real (tarea 1d: solo scaffold + datos mock, ver src/data/mock.ts). Las
// tareas 2b/3c/4b reemplazan cada `queryFn`/`mutationFn` mock por una llamada a `apiFetch`
// contra el endpoint real correspondiente -- la forma de los tipos (src/types/domain.ts) ya
// está pensada para no cambiar en ese momento.

export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
    public code: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

interface ErrorBody {
  detail: unknown;
  code: string;
}

export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`/api${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...init?.headers,
    },
  });

  if (!res.ok) {
    // Contrato uniforme de error (spec-010): {"detail": ..., "code": ...}.
    let body: ErrorBody = { detail: res.statusText, code: "http_error" };
    try {
      body = await res.json();
    } catch {
      // respuesta sin body JSON (poco frecuente dado app/errors.py) -- se usa el fallback.
    }
    throw new ApiError(
      typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail),
      res.status,
      body.code,
    );
  }

  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}
