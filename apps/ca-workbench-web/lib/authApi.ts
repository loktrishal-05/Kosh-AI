import type { SessionUser } from "./session.ts";
import { call } from "./tallyApi.ts";
export interface DemoInfo { enabled: boolean; label?: string; username?: string; password?: string }
export interface LoginResult { token: string; expires_in_s: number; user: SessionUser }
export const authApi = {
  /** Whether the server offers the one-click demo account, and what to fill in. */
  demoInfo: () => call<DemoInfo>("auth/demo-info"),
  login: (username: string, password: string) => call<LoginResult>("auth/login", { method: "POST", body: { username, password } }),
};
