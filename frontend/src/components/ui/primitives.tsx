import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

// ── Button ────────────────────────────────────────────────────

const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 rounded-lg text-sm font-medium transition-all duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500/50 disabled:pointer-events-none disabled:opacity-50 select-none",
  {
    variants: {
      variant: {
        primary:   "btn-gradient text-white",
        secondary: "bg-secondary border border-border text-muted-foreground hover:border-violet-500/40 hover:text-foreground",
        ghost:     "bg-transparent text-muted-foreground hover:bg-secondary hover:text-foreground",
        danger:    "bg-destructive/15 border border-destructive/30 text-red-400 hover:bg-destructive/25",
        outline:   "border border-border bg-transparent text-foreground hover:bg-secondary",
      },
      size: {
        sm:   "h-7 px-3 text-xs rounded-md",
        md:   "h-9 px-4",
        lg:   "h-11 px-6 text-base",
        icon: "h-9 w-9 p-0",
        "icon-sm": "h-7 w-7 p-0 rounded-md",
      },
    },
    defaultVariants: { variant: "secondary", size: "md" },
  }
);

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  loading?: boolean;
}

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, loading, children, disabled, ...props }, ref) => (
    <button
      ref={ref}
      className={cn(buttonVariants({ variant, size, className }))}
      disabled={disabled || loading}
      {...props}
    >
      {loading && (
        <svg className="w-4 h-4 animate-spin" viewBox="0 0 24 24" fill="none">
          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
        </svg>
      )}
      {children}
    </button>
  )
);
Button.displayName = "Button";

// ── Badge / Tag ───────────────────────────────────────────────

const badgeVariants = cva("tag font-medium", {
  variants: {
    variant: {
      violet:  "tag-violet",
      green:   "tag-green",
      amber:   "tag-amber",
      blue:    "tag-blue",
      red:     "tag-red",
      muted:   "tag-muted",
    },
  },
  defaultVariants: { variant: "muted" },
});

export interface BadgeProps
  extends React.HTMLAttributes<HTMLSpanElement>,
    VariantProps<typeof badgeVariants> {}

export function Badge({ className, variant, ...props }: BadgeProps) {
  return <span className={cn(badgeVariants({ variant, className }))} {...props} />;
}

// ── Card ──────────────────────────────────────────────────────

export function Card({
  className,
  children,
  ...props
}: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn("surface-card p-5", className)}
      {...props}
    >
      {children}
    </div>
  );
}

export function CardHeader({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("flex items-center justify-between mb-4", className)} {...props} />;
}

export function CardTitle({ className, ...props }: React.HTMLAttributes<HTMLParagraphElement>) {
  return (
    <p
      className={cn(
        "text-[11px] font-semibold text-muted-foreground uppercase tracking-widest",
        className
      )}
      {...props}
    />
  );
}

// ── Input ─────────────────────────────────────────────────────

export interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  error?: string;
}

export const Input = React.forwardRef<HTMLInputElement, InputProps>(
  ({ className, label, error, id, ...props }, ref) => {
    const inputId = id ?? label?.toLowerCase().replace(/\s/g, "-");
    return (
      <div className="space-y-1.5">
        {label && (
          <label htmlFor={inputId} className="text-xs font-medium text-muted-foreground">
            {label}
          </label>
        )}
        <input
          ref={ref}
          id={inputId}
          className={cn(
            "w-full h-9 px-3 bg-secondary border border-border rounded-lg text-sm text-foreground placeholder:text-muted-foreground",
            "focus:outline-none focus:border-violet-500/50 focus:ring-1 focus:ring-violet-500/30 transition-all",
            error && "border-destructive/60 focus:border-destructive focus:ring-destructive/30",
            className
          )}
          {...props}
        />
        {error && <p className="text-xs text-destructive">{error}</p>}
      </div>
    );
  }
);
Input.displayName = "Input";

// ── Textarea ──────────────────────────────────────────────────

export const Textarea = React.forwardRef<
  HTMLTextAreaElement,
  React.TextareaHTMLAttributes<HTMLTextAreaElement> & { label?: string; error?: string }
>(({ className, label, error, ...props }, ref) => (
  <div className="space-y-1.5">
    {label && <label className="text-xs font-medium text-muted-foreground">{label}</label>}
    <textarea
      ref={ref}
      className={cn(
        "w-full px-3 py-2.5 bg-secondary border border-border rounded-lg text-sm text-foreground placeholder:text-muted-foreground resize-none",
        "focus:outline-none focus:border-violet-500/50 focus:ring-1 focus:ring-violet-500/30 transition-all",
        className
      )}
      {...props}
    />
    {error && <p className="text-xs text-destructive">{error}</p>}
  </div>
));
Textarea.displayName = "Textarea";

// ── Progress ──────────────────────────────────────────────────

export function Progress({
  value,
  className,
  showLabel = false,
}: {
  value: number;
  className?: string;
  showLabel?: boolean;
}) {
  return (
    <div className={cn("space-y-1", className)}>
      {showLabel && (
        <p className="text-xs text-muted-foreground text-right">{value}%</p>
      )}
      <div className="h-1.5 bg-secondary rounded-full overflow-hidden">
        <div
          className="h-full rounded-full transition-all duration-500 ease-out"
          style={{
            width: `${Math.min(100, Math.max(0, value))}%`,
            background: "linear-gradient(90deg, #7c3aed, #a78bfa)",
          }}
        />
      </div>
    </div>
  );
}

// ── Skeleton ──────────────────────────────────────────────────

export function Skeleton({ className }: { className?: string }) {
  return <div className={cn("skeleton rounded-lg", className)} />;
}

export function SkeletonCard({ rows = 3 }: { rows?: number }) {
  return (
    <Card>
      <div className="space-y-3">
        <Skeleton className="h-4 w-32" />
        {Array.from({ length: rows }).map((_, i) => (
          <Skeleton key={i} className={`h-3 ${i % 2 === 0 ? "w-full" : "w-3/4"}`} />
        ))}
      </div>
    </Card>
  );
}

// ── Divider ───────────────────────────────────────────────────

export function Divider({ className }: { className?: string }) {
  return <div className={cn("h-px bg-border", className)} />;
}

// ── Empty state ───────────────────────────────────────────────

export function EmptyState({
  icon: Icon,
  title,
  description,
  action,
}: {
  icon: React.ElementType;
  title: string;
  description: string;
  action?: React.ReactNode;
}) {
  return (
    <div className="flex flex-col items-center justify-center py-16 px-6 text-center">
      <div className="w-14 h-14 rounded-2xl bg-violet-500/10 border border-violet-500/20 flex items-center justify-center mb-4">
        <Icon className="w-6 h-6 text-violet-400" />
      </div>
      <h3 className="font-display font-bold text-base text-foreground mb-1.5">{title}</h3>
      <p className="text-sm text-muted-foreground max-w-sm mb-5">{description}</p>
      {action}
    </div>
  );
}

// ── Waveform (decorative) ─────────────────────────────────────

export function Waveform({ bars = 12, className }: { bars?: number; className?: string }) {
  return (
    <div className={cn("flex items-center gap-0.5", className)}>
      {Array.from({ length: bars }).map((_, i) => (
        <div
          key={i}
          className="wave-bar"
          style={{
            height: `${30 + Math.random() * 70}%`,
            animationDelay: `${i * 0.1}s`,
          }}
        />
      ))}
    </div>
  );
}
