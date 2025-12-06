import { forwardRef, type HTMLAttributes } from "react";
import { cn } from "@/lib/utils";

export interface BadgeProps extends HTMLAttributes<HTMLSpanElement> {
  variant?: "default" | "success" | "warning" | "error" | "info" | "secondary";
  size?: "sm" | "md";
}

const variantStyles = {
  default: "bg-gray-100 text-gray-700",
  success: "bg-green-100 text-green-700",
  warning: "bg-yellow-100 text-yellow-700",
  error: "bg-red-100 text-red-700",
  info: "bg-blue-100 text-blue-700",
  secondary: "bg-purple-100 text-purple-700",
};

const sizeStyles = {
  sm: "px-1.5 py-0.5 text-xs",
  md: "px-2 py-1 text-xs",
};

export const Badge = forwardRef<HTMLSpanElement, BadgeProps>(
  ({ className, variant = "default", size = "md", children, ...props }, ref) => {
    return (
      <span
        ref={ref}
        className={cn(
          "inline-flex items-center font-medium rounded-full",
          variantStyles[variant],
          sizeStyles[size],
          className
        )}
        {...props}
      >
        {children}
      </span>
    );
  }
);

Badge.displayName = "Badge";

// Helper component for status badges with dot indicator
export interface StatusBadgeProps extends BadgeProps {
  showDot?: boolean;
}

export const StatusBadge = forwardRef<HTMLSpanElement, StatusBadgeProps>(
  ({ showDot = true, children, className, ...props }, ref) => {
    return (
      <Badge ref={ref} className={cn("gap-1.5", className)} {...props}>
        {showDot && (
          <span
            className={cn("w-1.5 h-1.5 rounded-full", {
              "bg-gray-500": props.variant === "default",
              "bg-green-500": props.variant === "success",
              "bg-yellow-500": props.variant === "warning",
              "bg-red-500": props.variant === "error",
              "bg-blue-500": props.variant === "info",
              "bg-purple-500": props.variant === "secondary",
            })}
          />
        )}
        {children}
      </Badge>
    );
  }
);

StatusBadge.displayName = "StatusBadge";
