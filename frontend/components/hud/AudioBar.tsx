"use client";

import { motion } from "framer-motion";
import * as React from "react";
import { cn } from "@/lib/utils/cn";

export interface AudioBarProps {
  listening: boolean;
  level?: number;
  className?: string;
}

const bars = Array.from({ length: 5 });

export function AudioBar({ listening, level = 0.2, className }: AudioBarProps) {
  const clamped = Math.min(Math.max(level, 0), 1);

  return (
    <div
      className={cn(
        "flex items-center gap-1 rounded-full border border-border bg-muted/40 px-3 py-2 text-xs uppercase tracking-[0.3em]",
        className
      )}
    >
      <span className="font-semibold text-muted-foreground">Mic</span>
      <div className="flex h-6 items-end gap-1">
        {bars.map((_, index) => {
          const height = listening ? 6 + Math.max(clamped * 28, 6) + index * 4 : 8;
          return (
            <motion.span
              key={index}
              className="w-[4px] rounded-full bg-accent"
              animate={{ height }}
              transition={{ repeat: listening ? Infinity : 0, duration: 0.4, repeatType: "mirror" }}
              style={{ height }}
            />
          );
        })}
      </div>
      <span className="ml-3 text-muted-foreground">{listening ? "listening" : "idle"}</span>
    </div>
  );
}
