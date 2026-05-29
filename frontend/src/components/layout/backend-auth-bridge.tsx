"use client";
/**
 * BackendAuthBridge
 *
 * After a user signs in via Clerk, this component automatically registers
 * or logs them into the backend's own JWT system and stores the tokens in
 * localStorage so all API calls work transparently.
 *
 * Strategy:
 *   password = "mm_" + first 32 chars of Clerk userId  (deterministic, stable)
 *   workspace slug = sanitised email local-part
 */

import { useEffect, useRef } from "react";
import { useUser } from "@clerk/nextjs";
import axios from "axios";
import { setTokens } from "@/services/api-client";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

function slugify(str: string): string {
  return str
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "")
    .slice(0, 60) || "workspace";
}

export function BackendAuthBridge() {
  const { user, isLoaded } = useUser();
  const attempted = useRef(false);

  useEffect(() => {
    if (!isLoaded || !user || attempted.current) return;
    // Already has a valid backend token — nothing to do
    if (typeof window !== "undefined" && localStorage.getItem("mm_access_token")) return;

    attempted.current = true;

    const email = user.primaryEmailAddress?.emailAddress ?? "";
    // Deterministic password derived from Clerk user ID — safe for local dev
    const password = `mm_${user.id.slice(0, 32)}`;
    const name = user.fullName || user.username || email.split("@")[0] || "User";
    const slug = slugify(email.split("@")[0]) || "workspace";

    async function syncBackendAuth() {
      // 1. Try login first (user may already exist)
      try {
        const res = await axios.post(`${API}/api/auth/login`, { email, password });
        setTokens(res.data.access_token, res.data.refresh_token);
        return;
      } catch {
        // 401 = wrong password or not registered yet → fall through to register
      }

      // 2. Register a new backend account
      try {
        const res = await axios.post(`${API}/api/auth/register`, {
          name,
          email,
          password,
          workspace: { name: `${name}'s Workspace`, slug },
        });
        setTokens(res.data.access_token, res.data.refresh_token);
      } catch (err: any) {
        // 400 "Email already registered" means a different password was used
        // (edge case: user was registered some other way). Try nothing more.
        console.warn("[BackendAuthBridge] Could not auto-register backend account:", err?.response?.data?.detail ?? err);
      }
    }

    syncBackendAuth();
  }, [isLoaded, user]);

  return null; // renders nothing
}
