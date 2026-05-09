import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

const routes = [
  {
    href: "/mirror",
    title: "Patient Mirror",
    description: "Full-screen AR coaching interface with live HUD overlays."
  },
  {
    href: "/practice",
    title: "Practice Mode",
    description: "Step-by-step guided repetitions with motivational feedback."
  },
  {
    href: "/progress",
    title: "Progress Tracker",
    description: "Gamified XP, streaks, and badge milestones for encouragement."
  },
  {
    href: "/encouragement",
    title: "Encouragement HUD",
    description: "Preview success, retry, and milestone overlays with TTS cues."
  },
  {
    href: "/dashboard",
    title: "Clinician Dashboard",
    description: "Monitor adherence and session metrics at a glance."
  }
];

export default function HomePage() {
  return (
    <section className="grid gap-6 py-6 md:grid-cols-2 xl:grid-cols-3">
      {routes.map((route) => (
        <Card key={route.href} className="flex flex-col justify-between gap-6">
          <CardHeader>
            <CardTitle className="text-3xl">{route.title}</CardTitle>
            <CardDescription className="text-base leading-relaxed text-muted-foreground">
              {route.description}
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Button asChild size="xl" className="w-full">
              <Link href={route.href}>Open {route.title}</Link>
            </Button>
          </CardContent>
        </Card>
      ))}
    </section>
  );
}
