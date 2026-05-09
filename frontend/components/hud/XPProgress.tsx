"use client";

import { motion } from "framer-motion";
import * as React from "react";
import { cn } from "@/lib/utils/cn";

export interface XPProgressProps {
  value: number;
  max?: number;
  streak?: number;
  className?: string;
}

export function XPProgress({ value, max = 1000, streak = 0, className }: XPProgressProps) {
  const progress = Math.min(Math.max(value / max, 0), 1);

  return (
    <div className={cn("flex w-full flex-col gap-3", className)}>
      <div className="flex items-end justify-between">
        <div>
          <p className="text-sm uppercase tracking-[0.4em] text-muted-foreground">XP Progress</p>
          <p className="font-display text-3xl font-semibold">{value.toLocaleString()} XP</p>
        </div>
        <div className="rounded-full border border-accent/50 bg-muted/30 px-4 py-1 text-sm font-medium text-accent">
          Streak {streak} days
        </div>
      </div>
      <div className="relative h-4 w-full overflow-hidden rounded-full border border-border bg-muted/40">
        <motion.div
          className="absolute inset-y-0 left-0 bg-accent"
          initial={{ width: 0 }}
          animate={{ width: `${progress * 100}%` }}
          transition={{ duration: 0.6, ease: "easeOut" }}
        />
      </div>
    </div>
  );
}
