import * as React from "react";
import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils/cn";

// Variant map adapted from 21st.dev CTA presets for healthcare UI scale.
const buttonVariants = cva(
  "inline-flex items-center justify-center rounded-md font-semibold transition-colors focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-offset-0 disabled:pointer-events-none disabled:opacity-60",
  {
    variants: {
      variant: {
        primary: "bg-primary text-primary-foreground shadow-glass hover:bg-primary/90",
        accent: "bg-accent text-accent-foreground shadow-hud hover:bg-accent/85",
        outline: "border border-border bg-transparent text-foreground hover:border-accent hover:text-accent",
        ghost: "text-foreground hover:bg-muted/60",
        warm: "bg-warm text-warm-foreground shadow-hud hover:bg-warm/90"
      },
      size: {
        lg: "h-12 min-w-[150px] px-6 text-lg",
        xl: "h-14 min-w-[200px] px-8 text-xl tracking-wide uppercase",
        md: "h-10 px-4 text-base",
        icon: "h-12 w-12"
      }
    },
    defaultVariants: {
      variant: "primary",
      size: "lg"
    }
  }
);

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean;
}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild = false, ...props }, ref) => {
    const Comp = asChild ? Slot : "button";

    return (
      <Comp
        className={cn(buttonVariants({ variant, size }), className)}
        ref={ref}
        {...props}
      />
    );
  }
);
Button.displayName = "Button";

export { Button, buttonVariants };
