import { api } from "./client";
import type { UserManual } from "./types";

export async function fetchUserManual(): Promise<UserManual> {
  const { data } = await api.get<UserManual>("/help/manual");
  return data;
}
