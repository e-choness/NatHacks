"use client";

import * as React from "react";
import { PracticeCard, type PracticeStatus } from "@/components/practice/PracticeCard";
import { EncouragementModal } from "@/components/hud/EncouragementModal";
import { XPProgress } from "@/components/hud/XPProgress";
import { useAppStore } from "@/lib/state/store";

const MOTIVATION_LINES = [
  "Great control on that repetition!",
  "Keep breathing steady — you're guiding the pace.",
  "That movement was smooth and confident!"
];

export default function PracticePage() {
  const routine = useAppStore((state) => state.routine);
  const session = useAppStore((state) => state.session);
  const actions = useAppStore((state) => state.actions);
  const currentStep = routine.steps[session.stepIndex];

  const [status, setStatus] = React.useState<PracticeStatus>("idle");
  const [completed, setCompleted] = React.useState(0);
  const [modalOpen, setModalOpen] = React.useState(false);
  const [motivation, setMotivation] = React.useState(MOTIVATION_LINES[0]);

  React.useEffect(() => {
    setMotivation(MOTIVATION_LINES[Math.floor(Math.random() * MOTIVATION_LINES.length)]);
  }, [session.stepIndex]);

  const handleStart = React.useCallback(() => {
    if (!currentStep) return;
    setStatus("running");
    actions.setOverlays({
      type: "overlay.set",
      shapes: [currentStep.overlay],
      hud: {
        title: routine.title,
        subtitle: currentStep.title,
        hint: currentStep.hint,
        step: `${session.stepIndex + 1} / ${routine.steps.length}`,
        max_time_s: currentStep.duration_s,
        time_left_s: currentStep.duration_s
      }
    });
  }, [actions, currentStep, routine.title, session.stepIndex]);

  const handlePause = React.useCallback(() => {
    setStatus("paused");
  }, []);

  const handleComplete = React.useCallback(() => {
    setStatus("complete");
    setCompleted((prev) => prev + 1);
    setModalOpen(true);
    actions.nextStep();
  }, [actions]);

  if (!currentStep) {
    return (
      <div className="rounded-3xl border border-border bg-card/80 p-10 text-lg text-muted-foreground">
        Routine loaded but no steps found.
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-8">
      <header className="flex flex-col gap-2">
        <p className="text-sm uppercase tracking-[0.35em] text-muted-foreground">Practice Mode</p>
        <h1 className="font-display text-4xl font-semibold">{routine.title}</h1>
        <p className="max-w-2xl text-lg text-muted-foreground">
          Guided reps with live overlays. Focus on smooth, accessible motion and breathing.
        </p>
      </header>

      <PracticeCard
        stepTitle={currentStep.title ?? currentStep.id}
        repetitions={5}
        completed={completed}
        status={status}
        motivation={motivation}
        onStart={handleStart}
        onPause={handlePause}
        onComplete={handleComplete}
      />

      <XPProgress value={session.xp} streak={session.streak} />

      <EncouragementModal
        open={modalOpen}
        onOpenChange={setModalOpen}
        tone={status === "complete" ? "success" : "encouragement"}
        title={status === "complete" ? "Nice work!" : "Keep it going"}
        subtitle={status === "complete" ? "That rep was steady and confident." : "Stay with the tempo."}
        hint={motivation}
        ctaLabel="Next Step"
        onCta={() => {
          setModalOpen(false);
          setStatus("idle");
          setCompleted(0);
        }}
      />
    </div>
  );
}
