"use client";
import { SignUp } from "@clerk/nextjs";

export default function RegisterPage() {
  return (
    <div className="min-h-screen bg-background flex items-center justify-center p-4">
      <div className="w-full max-w-md">
        <div className="text-center mb-8">
          <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-violet-500 to-violet-700 flex items-center justify-center mx-auto mb-4 shadow-lg shadow-violet-500/25">
            <span className="text-white text-xl">✦</span>
          </div>
          <h1 className="font-display font-bold text-2xl text-foreground">Create workspace</h1>
          <p className="text-sm text-muted-foreground mt-1">Start your free MeetingMind account</p>
        </div>
        <SignUp
          appearance={{
            elements: {
              rootBox: "w-full",
              card: "bg-card border border-border shadow-2xl rounded-2xl",
              headerTitle: "font-display text-foreground",
              formButtonPrimary: "btn-gradient",
              formFieldInput: "bg-secondary border-border text-foreground",
              footerActionLink: "text-violet-400 hover:text-violet-300",
            },
          }}
        />
      </div>
    </div>
  );
}
