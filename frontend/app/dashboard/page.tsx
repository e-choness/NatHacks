"use client";

import * as React from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { WeeklyBars } from "@/components/charts/WeeklyBars";

const overview = [
  { title: "Completion", value: "86%", description: "Across monitored routines" },
  { title: "Avg Reps", value: "4.8", description: "Per practice block" },
  { title: "Success", value: "92%", description: "Voice command recognition" }
];

const clinicianFeed = [
  { name: "Alex P.", note: "Completed practice with new overlay" },
  { name: "Morgan L.", note: "Requested brighter HUD" },
  { name: "Jamie T.", note: "Shave routine improved 20%" }
];

const weekly = [
  { label: "Week 1", value: 18 },
  { label: "Week 2", value: 21 },
  { label: "Week 3", value: 26 },
  { label: "Week 4", value: 28 },
  { label: "Week 5", value: 30 },
  { label: "Week 6", value: 33 },
  { label: "Week 7", value: 34 }
];

export default function DashboardPage() {
  return (
    <div className="flex flex-col gap-8">
      <header className="space-y-2">
        <p className="text-sm uppercase tracking-[0.35em] text-muted-foreground">Clinician Dashboard</p>
        <h1 className="font-display text-4xl font-semibold">Care overview</h1>
        <p className="max-w-2xl text-lg text-muted-foreground">
          Snapshot of adherence, repetitions, and recognition so clinicians can tailor follow-up sessions.
        </p>
      </header>

      <section className="grid gap-4 md:grid-cols-3">
        {overview.map((metric) => (
          <Card key={metric.title} className="border-border/60">
            <CardHeader>
              <CardTitle className="text-sm uppercase tracking-[0.4em] text-muted-foreground">
                {metric.title}
              </CardTitle>
            </CardHeader>
            <CardContent>
              <p className="font-display text-4xl font-semibold text-accent">{metric.value}</p>
              <p className="text-sm text-muted-foreground">{metric.description}</p>
            </CardContent>
          </Card>
        ))}
      </section>

      <Card className="border-border/60">
        <CardHeader>
          <CardTitle className="text-2xl">Weekly Coaching Sessions</CardTitle>
          <CardDescription>Trend for patient touchpoints with the smart mirror backup.</CardDescription>
        </CardHeader>
        <CardContent>
          <WeeklyBars data={weekly} highlightIndex={weekly.length - 1} className="grid-cols-7" />
        </CardContent>
      </Card>

      <Card className="border-border/60">
        <CardHeader>
          <CardTitle className="text-2xl">Patient Notes</CardTitle>
          <CardDescription>Recent feedback requiring clinician follow-up.</CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-3">
          {clinicianFeed.map((entry) => (
            <div key={entry.name} className="rounded-xl border border-border/60 bg-muted/30 px-4 py-3">
              <p className="font-semibold text-foreground">{entry.name}</p>
              <p className="text-sm text-muted-foreground">{entry.note}</p>
            </div>
          ))}
        </CardContent>
      </Card>
    </div>
  );
}
