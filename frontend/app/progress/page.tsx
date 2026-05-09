"use client";

import * as React from "react";
import { WeeklyBars } from "@/components/charts/WeeklyBars";
import { XPProgress } from "@/components/hud/XPProgress";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useAppStore } from "@/lib/state/store";
import { motion } from "framer-motion";

const weeklyData = [
  { label: "Mon", value: 3 },
  { label: "Tue", value: 4 },
  { label: "Wed", value: 5 },
  { label: "Thu", value: 4 },
  { label: "Fri", value: 6 },
  { label: "Sat", value: 5 },
  { label: "Sun", value: 7 }
];

const badges = [
  { label: "Steady Sunrise", description: "Complete the routine 5 mornings in a row." },
  { label: "Confidence Boost", description: "Earn 300 XP in a single session." },
  { label: "Clinician Kudos", description: "Share progress with your clinician." }
];

export default function ProgressPage() {
  const session = useAppStore((state) => state.session);

  return (
    <div className="flex flex-col gap-8">
      <header className="space-y-2">
        <p className="text-sm uppercase tracking-[0.35em] text-muted-foreground">Progress Tracker</p>
        <h1 className="font-display text-4xl font-semibold">Keep the momentum</h1>
        <p className="max-w-2xl text-lg text-muted-foreground">
          XP growth, streaks, and badges make daily care feel rewarding. Celebrate wins and stay inspired.
        </p>
      </header>

      <XPProgress value={session.xp} streak={session.streak} className="max-w-3xl" />

      <Card className="border-border/60">
        <CardHeader>
          <CardTitle className="text-2xl">Weekly Repetitions</CardTitle>
        </CardHeader>
        <CardContent>
          <WeeklyBars data={weeklyData} highlightIndex={6} />
        </CardContent>
      </Card>

      <section className="grid gap-4 md:grid-cols-3">
        {badges.map((badge, index) => (
          <motion.div
            key={badge.label}
            className="rounded-2xl border border-border bg-card/70 p-6 shadow-glass"
            initial={{ opacity: 0, y: 24 }}
            whileInView={{ opacity: 1, y: 0 }}
            transition={{ delay: index * 0.1, duration: 0.4, ease: "easeOut" }}
          >
            <p className="text-sm uppercase tracking-[0.3em] text-accent">Badge</p>
            <h3 className="font-display text-2xl font-semibold">{badge.label}</h3>
            <p className="mt-2 text-sm text-muted-foreground">{badge.description}</p>
          </motion.div>
        ))}
      </section>
    </div>
  );
}
