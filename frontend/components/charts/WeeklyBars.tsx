"use client";

import { motion } from "framer-motion";
import * as React from "react";
import { cn } from "@/lib/utils/cn";

type WeeklyDatum = {
  label: string;
  value: number;
  target?: number;
};

export interface WeeklyBarsProps {
  data: WeeklyDatum[];
  highlightIndex?: number;
  className?: string;
}

export function WeeklyBars({ data, highlightIndex, className }: WeeklyBarsProps) {
  const max = Math.max(...data.map((item) => item.value), 1);

  return (
    <div className={cn("grid grid-cols-7 gap-4", className)}>
      {data.map((item, index) => {
        const height = (item.value / max) * 140;
        const isHighlight = highlightIndex === index;
        return (
          <div key={item.label} className="flex flex-col items-center gap-3">
            <motion.div
              className={cn(
                "flex h-40 w-6 items-end rounded-full border border-border bg-muted/40",
                isHighlight && "border-accent bg-accent/20"
              )}
            >
              <motion.div
                className={cn("w-full rounded-full bg-accent", isHighlight && "bg-warm")}
                initial={{ height: 0 }}
                animate={{ height }}
                transition={{ duration: 0.5, ease: "easeOut" }}
              />
            </motion.div>
            <div className="text-center text-sm text-muted-foreground">
              <p className="font-medium text-foreground">{item.value}</p>
              <p>{item.label}</p>
            </div>
          </div>
        );
      })}
    </div>
  );
}
