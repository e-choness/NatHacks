"use client";

import { motion, AnimatePresence } from "framer-motion";
import * as React from "react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle
} from "@/components/ui/dialog";
import { cn } from "@/lib/utils/cn";

export type EncouragementTone = "success" | "retry" | "milestone" | "encouragement";

export interface EncouragementModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  tone?: EncouragementTone;
  title: string;
  subtitle?: string;
  hint?: string;
  ctaLabel?: string;
  onCta?: () => void;
}

const toneColors: Record<EncouragementTone, string> = {
  success: "bg-emerald-500/20 text-emerald-200 border-emerald-400/50",
  retry: "bg-red-500/15 text-red-200 border-red-400/40",
  milestone: "bg-amber-500/20 text-amber-100 border-amber-400/50",
  encouragement: "bg-sky-500/15 text-sky-100 border-sky-400/50"
};

export function EncouragementModal({
  open,
  onOpenChange,
  tone = "encouragement",
  title,
  subtitle,
  hint,
  ctaLabel = "Continue",
  onCta
}: EncouragementModalProps) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="overflow-hidden">
        <DialogHeader className="space-y-4">
          <div className={cn("rounded-2xl border px-4 py-2 text-sm font-semibold uppercase", toneColors[tone])}>
            {tone === "success" && "Success"}
            {tone === "retry" && "Try Again"}
            {tone === "milestone" && "Milestone"}
            {tone === "encouragement" && "Encouragement"}
          </div>
          <DialogTitle className="font-display text-3xl text-foreground">{title}</DialogTitle>
          {subtitle ? (
            <DialogDescription className="text-lg leading-relaxed text-muted-foreground">
              {subtitle}
            </DialogDescription>
          ) : null}
        </DialogHeader>
        <AnimatePresence>
          {hint ? (
            <motion.div
              key={hint}
              initial={{ opacity: 0, y: 16 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -12 }}
              transition={{ duration: 0.3, ease: "easeOut" }}
              className="rounded-xl border border-border/40 bg-muted/40 p-4 text-base text-muted-foreground"
            >
              {hint}
            </motion.div>
          ) : null}
        </AnimatePresence>
        <div className="flex items-center justify-end gap-3 pt-4">
          <Button variant="ghost" onClick={() => onOpenChange(false)}>
            Close
          </Button>
          <Button onClick={onCta ?? (() => onOpenChange(false))} size="lg">
            {ctaLabel}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
