"use client";

import * as React from "react";
import { CameraSurface } from "@/components/camera/CameraSurface";
import { Button } from "@/components/ui/button";
import { AudioBar } from "@/components/hud/AudioBar";
import { useAppStore } from "@/lib/state/store";
import type { BackendMessage } from "@/lib/cv/messages";
import { createVoiceAssistant, type VoiceAssistantHandle } from "@/lib/voice/assistant";
import {
  advanceTask,
  fetchTasks,
  getCurrentTask,
  replayStepTts,
  startSession,
  startTask,
  stopTask,
  type TaskSummary
} from "@/lib/api/tasks";
import { buildBackendWsUrl, BACKEND_BASE_URL } from "@/lib/config/env";

type VoiceLogEntry = {
  role: "user" | "assistant";
  text: string;
};

export default function MirrorPage() {
  const actions = useAppStore((state) => state.actions);
  const overlays = useAppStore((state) => state.overlays);
  const status = useAppStore((state) => state.status);
  const [tasks, setTasks] = React.useState<TaskSummary[]>([]);
  const [selectedTaskId, setSelectedTaskId] = React.useState<string | null>(null);
  const [sessionActive, setSessionActive] = React.useState(false);
  const [listening, setListening] = React.useState(false);
  const [level, setLevel] = React.useState(0);
  const [voiceLog, setVoiceLog] = React.useState<VoiceLogEntry[]>([]);
  const [isLoading, setIsLoading] = React.useState(false);
  const [currentStep, setCurrentStep] = React.useState<{ index: number; total: number } | null>(null);
  const assistantRef = React.useRef<VoiceAssistantHandle | null>(null);
  const lastTranscriptRef = React.useRef<string | undefined>(undefined);

  const appendVoiceLog = React.useCallback((entry: VoiceLogEntry) => {
    setVoiceLog((prev) => [...prev.slice(-7), entry]);
  }, []);

  const refreshTaskState = React.useCallback(async () => {
    try {
      const info = await getCurrentTask();
      if (info.active && info.current_step && info.total_steps) {
        setCurrentStep({ index: info.current_step, total: info.total_steps });
        setSessionActive(true);
      } else {
        setCurrentStep(null);
        setSessionActive(false);
      }
    } catch (error) {
      console.warn("Failed to refresh task state", error);
    }
  }, []);

  React.useEffect(() => {
    let cancelled = false;
    fetchTasks()
      .then((items) => {
        if (cancelled) return;
        setTasks(items);
        if (items.length) {
          setSelectedTaskId((current) => current ?? items[0].task_id);
        }
      })
      .catch((error) => console.error("Failed to load tasks", error));
    void refreshTaskState();
    return () => {
      cancelled = true;
    };
  }, [refreshTaskState]);

  React.useEffect(() => {
    if (typeof window === "undefined") return;
    const ws = new WebSocket(buildBackendWsUrl("/ws"));
    ws.onmessage = (event) => {
      try {
        const message = JSON.parse(event.data) as BackendMessage;
        if (message.type === "overlay.set") {
          actions.setOverlays({ ...message, source: "remote" });
        } else if (message.type === "overlay.clear") {
          actions.setOverlays(null);
        } else if (message.type === "status") {
          actions.setStatus({
            camera: typeof message.camera === "string" ? message.camera : undefined,
            lighting: typeof message.lighting === "string" ? message.lighting : undefined,
            fps: typeof message.fps === "number" ? message.fps : undefined,
            latency_ms: typeof message.latency_ms === "number" ? message.latency_ms : undefined,
            reduce_motion: typeof message.reduce_motion === "boolean" ? message.reduce_motion : undefined
          });
        } else if (message.type === "tts") {
          actions.recordTts(message.text);
          appendVoiceLog({ role: "assistant", text: message.text });
        }
      } catch (error) {
        console.warn("Bad WS payload", error);
      }
    };
    ws.onerror = (error) => console.warn("WebSocket error", error);
    return () => ws.close(1000, "mirror navigation");
  }, [actions, appendVoiceLog]);

  const handleStart = React.useCallback(async () => {
    if (!selectedTaskId) return;
    setIsLoading(true);
    try {
      await startSession({ patient_id: "demo-user", routine_id: selectedTaskId });
      await startTask(selectedTaskId);
      appendVoiceLog({ role: "assistant", text: `Starting ${selectedTaskId.replaceAll("_", " ")}` });
      await refreshTaskState();
    } catch (error) {
      console.error("Failed to start task", error);
      appendVoiceLog({ role: "assistant", text: "Unable to start the routine." });
    } finally {
      setIsLoading(false);
    }
  }, [appendVoiceLog, refreshTaskState, selectedTaskId]);

  const handleNext = React.useCallback(async () => {
    setIsLoading(true);
    try {
      const result = await advanceTask();
      if (result.task_complete) {
        appendVoiceLog({ role: "assistant", text: "Routine complete. Great job!" });
        setSessionActive(false);
        actions.setOverlays(null);
        setCurrentStep(null);
      } else if (result.ok) {
        appendVoiceLog({ role: "assistant", text: "Advancing to the next step." });
        await refreshTaskState();
      } else if (result.reason) {
        appendVoiceLog({ role: "assistant", text: result.reason });
      }
    } catch (error) {
      console.error("Failed to advance", error);
      appendVoiceLog({ role: "assistant", text: "Unable to advance. Try again." });
    } finally {
      setIsLoading(false);
    }
  }, [actions, appendVoiceLog, refreshTaskState]);

  const handleStop = React.useCallback(async () => {
    setIsLoading(true);
    try {
      await stopTask();
      actions.setOverlays(null);
      setSessionActive(false);
      setCurrentStep(null);
      appendVoiceLog({ role: "assistant", text: "Routine stopped." });
    } catch (error) {
      console.error("Failed to stop task", error);
    } finally {
      setIsLoading(false);
    }
  }, [actions, appendVoiceLog]);

  const handleReplay = React.useCallback(async () => {
    try {
      const result = await replayStepTts();
      if (!result.ok && result.reason) {
        appendVoiceLog({ role: "assistant", text: result.reason });
      }
    } catch (error) {
      console.warn("Replay failed", error);
    }
  }, [appendVoiceLog]);

  React.useEffect(() => {
    const assistant = createVoiceAssistant({ backendUrl: BACKEND_BASE_URL });
    assistantRef.current = assistant;
    if (!assistant) {
      appendVoiceLog({ role: "assistant", text: "Browser voice recognition enabled as fallback." });
      return;
    }
    const unsubscribe = assistant.on((event) => {
      if (event.type === "listening") {
        setListening(event.active);
        if (!event.active) {
          setLevel(0);
        }
      }
      if (event.type === "level") {
        setLevel(event.value);
      }
      if (event.type === "response") {
        if (event.transcript && event.transcript !== lastTranscriptRef.current) {
          appendVoiceLog({ role: "user", text: event.transcript });
          lastTranscriptRef.current = event.transcript;
        }
        if (event.text) {
          appendVoiceLog({ role: "assistant", text: event.text });
        }
      }
      if (event.type === "command") {
        if (!event.transcript || event.transcript !== lastTranscriptRef.current) {
          appendVoiceLog({ role: "user", text: event.transcript ?? event.command });
          lastTranscriptRef.current = event.transcript;
        }
        const command = event.command;
        if (command === "start tutorial") {
          void handleStart();
        } else if (command === "next") {
          void handleNext();
        } else if (command === "pause") {
          void handleStop();
        } else if (command === "repeat hint") {
          void handleReplay();
        }
      }
      if (event.type === "error") {
        appendVoiceLog({ role: "assistant", text: `Mic error: ${event.message}` });
      }
    });
    return () => {
      unsubscribe?.();
      assistant.stop();
    };
  }, [appendVoiceLog, handleNext, handleReplay, handleStart, handleStop]);

  return (
    <div className="flex flex-col gap-8">
      <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
        <div className="space-y-2">
          <p className="text-sm uppercase tracking-[0.35em] text-muted-foreground">Patient Mirror</p>
          <h2 className="font-display text-4xl font-semibold">Live AR Guidance</h2>
          <p className="max-w-2xl text-lg text-muted-foreground">
            Capture patient movements, stream overlays from the Assistive Coach backend, and drive routines with
            Vertex-powered voice assistance.
          </p>
        </div>
        <div className="flex flex-wrap gap-3">
          <select
            className="rounded-xl border border-border bg-card px-4 py-2 text-base shadow-sm"
            value={selectedTaskId ?? ""}
            onChange={(event) => setSelectedTaskId(event.target.value || null)}
            aria-label="Select routine"
          >
            {tasks.map((task) => (
              <option key={task.task_id} value={task.task_id}>
                {task.name}
              </option>
            ))}
          </select>
          <Button
            variant="outline"
            size="lg"
            onClick={() => assistantRef.current?.toggle()}
            aria-pressed={listening}
          >
            {listening ? "Mic On" : "Mic Off"}
          </Button>
        </div>
      </div>

      <AudioBar listening={listening} level={level} className="max-w-xs" />

      <CameraSurface />

      <div className="flex flex-wrap items-center justify-between gap-4">
        <div className="flex flex-wrap gap-3">
          <Button onClick={() => void handleStart()} size="xl" disabled={!selectedTaskId || isLoading}>
            Start Routine
          </Button>
          <Button onClick={() => void handleNext()} size="lg" disabled={!sessionActive || isLoading}>
            Next Step
          </Button>
          <Button
            variant="outline"
            size="lg"
            onClick={() => void handleReplay()}
            disabled={!sessionActive || isLoading}
          >
            Repeat Prompt
          </Button>
          <Button variant="ghost" onClick={() => void handleStop()} size="lg" disabled={!sessionActive || isLoading}>
            Stop
          </Button>
        </div>
        <div className="text-sm text-muted-foreground">
          {currentStep
            ? `Step ${currentStep.index} of ${currentStep.total}`
            : sessionActive
              ? "Waiting for next overlay"
              : "Routine idle"}
        </div>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        <div className="rounded-3xl border border-border bg-card/70 p-6 text-sm">
          <h3 className="mb-4 font-display text-lg font-semibold uppercase tracking-[0.2em] text-muted-foreground">
            System Status
          </h3>
          <dl className="grid grid-cols-2 gap-3">
            <div>
              <dt className="text-xs uppercase tracking-[0.3em] text-muted-foreground">Camera</dt>
              <dd className="text-base font-medium">{status?.camera ?? "unknown"}</dd>
            </div>
            <div>
              <dt className="text-xs uppercase tracking-[0.3em] text-muted-foreground">Lighting</dt>
              <dd className="text-base font-medium">{status?.lighting ?? "unknown"}</dd>
            </div>
            <div>
              <dt className="text-xs uppercase tracking-[0.3em] text-muted-foreground">FPS</dt>
              <dd className="text-base font-medium">{status?.fps?.toFixed?.(1) ?? "--"}</dd>
            </div>
            <div>
              <dt className="text-xs uppercase tracking-[0.3em] text-muted-foreground">Latency</dt>
              <dd className="text-base font-medium">
                {status?.latency_ms ? `${Math.round(status.latency_ms)} ms` : "--"}
              </dd>
            </div>
          </dl>
        </div>

        <div className="rounded-3xl border border-border bg-card/70 p-6 text-sm">
          <h3 className="mb-4 font-display text-lg font-semibold uppercase tracking-[0.2em] text-muted-foreground">
            Voice Transcript
          </h3>
          <div className="flex max-h-48 flex-col gap-2 overflow-y-auto">
            {voiceLog.length === 0 && <div className="text-muted-foreground">Voice assistant idle.</div>}
            {voiceLog.map((entry, index) => (
              <div key={index} className="rounded-xl bg-muted/40 px-3 py-2">
                <span className="text-xs uppercase tracking-[0.3em] text-muted-foreground">
                  {entry.role === "user" ? "User" : "Assistant"}
                </span>
                <p className="text-sm font-medium text-foreground">{entry.text}</p>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="rounded-full border border-border bg-muted/40 px-6 py-4 text-sm font-medium uppercase tracking-[0.3em] text-muted-foreground">
        Daily encouragement ticker · Upcoming appointment with Dr. Laurent · Hydrate and take a mindful breath
      </div>
    </div>
  );
}
