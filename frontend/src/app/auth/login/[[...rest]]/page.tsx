// src/app/auth/login/[[...rest]]/page.tsx
// Catch-all route required by Clerk for SSO callbacks, MFA, etc.
"use client";

import { SignIn } from "@clerk/nextjs";

export default function LoginPage() {
  return (
    <div className="min-h-screen bg-background flex items-center justify-center p-4">
      <div className="w-full max-w-md">
        <div className="text-center mb-8">
          <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-violet-500 to-violet-700 flex items-center justify-center mx-auto mb-4 shadow-lg shadow-violet-500/25">
            <span className="text-white text-xl">✦</span>
          </div>
          <h1 className="font-display font-bold text-2xl text-foreground">MeetingMind AI</h1>
          <p className="text-sm text-muted-foreground mt-1">Sign in to your workspace</p>
        </div>
        <SignIn
          appearance={{
            elements: {
              rootBox: "w-full",
              card: "bg-card border border-border shadow-2xl rounded-2xl",
              headerTitle: "font-display text-foreground",
              headerSubtitle: "text-muted-foreground",
              formButtonPrimary: "btn-gradient",
              formFieldInput: "bg-secondary border-border text-foreground",
              footerActionLink: "text-violet-400 hover:text-violet-300",
              identityPreviewText: "text-foreground",
              identityPreviewEditButton: "text-violet-400",
            },
          }}
        />
      </div>
    </div>
  );
}
