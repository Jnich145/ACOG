import { cn } from "@/lib/utils";

export interface SpinnerProps {
  size?: "sm" | "md" | "lg";
  className?: string;
}

const sizeStyles = {
  sm: "h-4 w-4 border-2",
  md: "h-6 w-6 border-2",
  lg: "h-8 w-8 border-3",
};

export function Spinner({ size = "md", className }: SpinnerProps) {
  return (
    <div
      className={cn(
        "animate-spin rounded-full border-gray-300 border-t-primary-600",
        sizeStyles[size],
        className
      )}
      role="status"
      aria-label="Loading"
    >
      <span className="sr-only">Loading...</span>
    </div>
  );
}

// Full page loading spinner
export function LoadingScreen() {
  return (
    <div className="flex h-full min-h-[200px] items-center justify-center">
      <Spinner size="lg" />
    </div>
  );
}

// Inline loading indicator with text
export interface LoadingTextProps {
  text?: string;
  size?: "sm" | "md" | "lg";
}

export function LoadingText({ text = "Loading...", size = "md" }: LoadingTextProps) {
  return (
    <div className="flex items-center gap-2 text-gray-500">
      <Spinner size={size} />
      <span className="text-sm">{text}</span>
    </div>
  );
}
