"use client";

import { motion } from "framer-motion";
import * as React from "react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils/cn";

export type PracticeStatus = "idle" | "running" | "paused" | "complete";

export interface PracticeCardProps {
  stepTitle: string;
  repetitions: number;
  completed: number;
  status: PracticeStatus;
  motivation?: string;
  onStart: () => void;
  onPause: () => void;
  onComplete: () => void;
}

export function PracticeCard({
  stepTitle,
  repetitions,
  completed,
  status,
  motivation,
  onStart,
  onPause,
  onComplete
}: PracticeCardProps) {
  const progress = Math.min(Math.max(completed / repetitions, 0), 1);
  const displayStatus = status === "running" ? "In progress" : status === "paused" ? "Paused" : status === "complete" ? "Complete" : "Ready";

  return (
    <div className="flex flex-col gap-6 rounded-3xl border border-border bg-card/80 p-8 shadow-glass">
      <header className="flex flex-col gap-2">
        <span className="text-sm uppercase tracking-[0.35em] text-muted-foreground">Practice Mode</span>
        <h2 className="font-display text-4xl font-semibold">{stepTitle}</h2>
        <p className="text-lg text-muted-foreground">{displayStatus} · {completed}/{repetitions} reps</p>
      </header>

      <div className="flex flex-col gap-6 md:flex-row md:items-center md:justify-between">
        <div className="flex items-center gap-6">
          <ProgressRing progress={progress} />
          <div>
            <p className="text-sm uppercase tracking-[0.3em] text-muted-foreground">Repetitions</p>
            <p className="font-display text-5xl font-bold">{completed}</p>
            <p className="text-lg text-muted-foreground">Target {repetitions}</p>
          </div>
        </div>
        <div className="flex flex-col gap-3 md:items-end">
          <div className="flex gap-3">
            {status !== "running" && status !== "complete" ? (
              <Button size="xl" onClick={onStart}>
                Start
              </Button>
            ) : null}
            {status === "running" ? (
              <Button variant="outline" size="lg" onClick={onPause}>
                Pause
              </Button>
            ) : null}
            {(status === "paused" || status === "running") && (
              <Button variant="accent" size="lg" onClick={onComplete}>
                Complete Step
              </Button>
            )}
          </div>
          {motivation ? (
            <p className="max-w-sm text-right text-base text-accent">{motivation}</p>
          ) : null}
        </div>
      </div>
    </div>
  );
}

interface ProgressRingProps {
  progress: number;
}

function ProgressRing({ progress }: ProgressRingProps) {
  const radius = 72;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference * (1 - progress);

  return (
    <div className="relative h-40 w-40">
      <svg viewBox="0 0 200 200" className="h-full w-full rotate-[-90deg]">
        <circle
          cx="100"
          cy="100"
          r={radius}
          stroke="rgba(255,255,255,0.15)"
          strokeWidth="16"
          fill="transparent"
        />
        <motion.circle
          cx="100"
          cy="100"
          r={radius}
          stroke="rgba(14,165,164,0.95)"
          strokeWidth="16"
          fill="transparent"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          strokeLinecap="round"
          animate={{ strokeDashoffset: offset }}
          transition={{ duration: 0.5, ease: "easeOut" }}
        />
      </svg>
      <div className="absolute inset-0 flex items-center justify-center">
        <span className="font-display text-3xl font-semibold text-accent">{Math.round(progress * 100)}%</span>
      </div>
    </div>
  );
}
