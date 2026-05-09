"use client";

import * as React from "react";
import { EncouragementModal, type EncouragementTone } from "@/components/hud/EncouragementModal";
import { AudioBar } from "@/components/hud/AudioBar";
import { Button } from "@/components/ui/button";

export default function EncouragementPage() {
  const [open, setOpen] = React.useState(false);
  const [tone, setTone] = React.useState<EncouragementTone>("encouragement");
  const [listening, setListening] = React.useState(false);

  const preview = (nextTone: EncouragementTone) => {
    setTone(nextTone);
    setOpen(true);
  };

  return (
    <div className="flex flex-col gap-8">
      <header className="space-y-2">
        <p className="text-sm uppercase tracking-[0.35em] text-muted-foreground">Encouragement HUD</p>
        <h1 className="font-display text-4xl font-semibold">Preview supportive overlays</h1>
        <p className="max-w-2xl text-lg text-muted-foreground">
          Trigger success, retry, milestone, or general encouragement messages with accessible typography and tone.
        </p>
      </header>

      <div className="flex flex-wrap gap-4">
        <Button onClick={() => preview("success")} size="lg">
          Preview Success
        </Button>
        <Button onClick={() => preview("retry")} size="lg" variant="outline">
          Preview Retry
        </Button>
        <Button onClick={() => preview("milestone")} size="lg" variant="accent">
          Preview Milestone
        </Button>
        <Button onClick={() => preview("encouragement")} size="lg" variant="ghost">
          Preview Encouragement
        </Button>
      </div>

      <AudioBar listening={listening} className="max-w-sm" />
      <div className="flex gap-3">
        <Button onClick={() => setListening((value) => !value)} size="lg">
          {listening ? "Stop Listening" : "Start Listening"}
        </Button>
        <Button variant="outline" size="lg">
          Toggle Sound
        </Button>
      </div>

      <EncouragementModal
        open={open}
        onOpenChange={setOpen}
        tone={tone}
        title={tone === "success" ? "Success!" : tone === "retry" ? "Let's retry" : tone === "milestone" ? "Milestone unlocked" : "You're doing great"}
        subtitle={tone === "milestone" ? "You've reached 7 consecutive sessions." : "This is how progress feels."}
        hint={tone === "retry" ? "Take a breath and try a slightly slower movement." : "Keep your shoulders relaxed and eyes forward."}
        ctaLabel="Got it"
      />
    </div>
  );
}
