import { useQuery } from "@tanstack/react-query";
import { useEffect } from "react";
import { api, ApiError, type KidneyState } from "./api";
import { useSession } from "@/store/session";

/** The signed-in patient's Living Kidney state. Also drives the app-wide accent theme. */
export function useMyKidney() {
  const user = useSession((s) => s.user);
  const setKidney = useSession((s) => s.setKidney);
  const enabled = !!user && (user.role === "patient" || user.role === "caregiver");
  const q = useQuery<KidneyState, ApiError>({
    queryKey: ["kidney", "me"],
    queryFn: () => api.myKidney(),
    enabled,
    retry: (n, e) => !(e instanceof ApiError && (e.status === 422 || e.status === 401 || e.status === 403)) && n < 1,
  });
  useEffect(() => {
    if (q.data) setKidney(q.data);
  }, [q.data, setKidney]);
  return q;
}

export const isPatientLike = (role?: string) => role === "patient" || role === "caregiver";

export function homeFor(role: string) {
  return role === "doctor" ? "/doctor" : role === "admin" ? "/admin" : "/home";
}
