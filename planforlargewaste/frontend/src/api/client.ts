import axios, { AxiosError } from "axios";

/** 화면에 보여 줄 오류. 서버의 공통 오류 형식 {error:{code,message}}를 변환한다. */
export class ApiError extends Error {
  code: string;
  status: number | null;
  constructor(code: string, message: string, status: number | null) {
    super(message);
    this.code = code;
    this.status = status;
  }
}

export const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8001",
  timeout: 25_000,
});

api.interceptors.response.use(
  (res) => res,
  (err: AxiosError<{ error?: { code?: string; message?: string } }>) => {
    const body = err.response?.data?.error;
    if (body?.message) return Promise.reject(new ApiError(body.code ?? "ERROR", body.message, err.response?.status ?? null));
    if (err.code === "ECONNABORTED")
      return Promise.reject(new ApiError("TIMEOUT", "응답이 지연되고 있습니다. 잠시 후 다시 시도하십시오.", null));
    return Promise.reject(new ApiError("NETWORK", "서버에 연결할 수 없습니다. 잠시 후 다시 시도하십시오.", null));
  },
);
