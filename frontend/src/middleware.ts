import { clerkMiddleware, createRouteMatcher } from "@clerk/nextjs/server";
import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

const isPublicRoute = createRouteMatcher([
  "/auth/login(.*)",
  "/auth/register(.*)",
  "/api/webhooks(.*)",
]);

// ── Development bypass: skip Clerk auth if keys are placeholder values ──
const isDev =
  process.env.NODE_ENV === "development" &&
  (!process.env.CLERK_SECRET_KEY ||
    process.env.CLERK_SECRET_KEY.startsWith("sk_test_REPLACE"));

export default isDev
  ? function devMiddleware(_request: NextRequest) {
      // In dev without valid keys: allow all requests through
      return NextResponse.next();
    }
  : clerkMiddleware((auth, request) => {
      if (!isPublicRoute(request)) {
        auth.protect();
      }
    });

export const config = {
  matcher: [
    "/((?!_next|[^?]*\\.(?:html?|css|js(?!on)|jpe?g|webp|png|gif|svg|ttf|woff2?|ico|csv|docx?|xlsx?|zip|webmanifest)).*)",
    "/(api|trpc)(.*)",
  ],
};
