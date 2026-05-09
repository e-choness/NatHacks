"use client";

import { usePathname, useRouter } from "next/navigation";
import * as React from "react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

type NavTab = {
  value: string;
  label: string;
  href: string;
};

const TABS: NavTab[] = [
  { value: "mirror", label: "Patient Mirror", href: "/mirror" },
  { value: "practice", label: "Practice Mode", href: "/practice" },
  { value: "progress", label: "Progress Tracker", href: "/progress" },
  { value: "encouragement", label: "Encouragement", href: "/encouragement" },
  { value: "dashboard", label: "Clinician Dashboard", href: "/dashboard" }
];

export function AppNavTabs() {
  const pathname = usePathname();
  const router = useRouter();
  const [value, setValue] = React.useState<string>(() => getValueFromPath(pathname));

  React.useEffect(() => {
    setValue(getValueFromPath(pathname));
  }, [pathname]);

  return (
    <Tabs
      value={value}
  onValueChange={(next: string) => {
        const tab = TABS.find((item) => item.value === next);
        if (!tab) return;
        setValue(next);
        router.push(tab.href);
      }}
    >
      <TabsList aria-label="Navigate assistive mirror views" className="mx-auto w-full max-w-5xl">
        {TABS.map((tab) => (
          <TabsTrigger key={tab.value} value={tab.value} className="flex-1 min-h-[48px]">
            {tab.label}
          </TabsTrigger>
        ))}
      </TabsList>
      {/* Content panels are rendered by Next routes; we expose hidden containers for accessibility */}
      {TABS.map((tab) => (
        <TabsContent key={tab.value} value={tab.value} className="sr-only">
          {tab.label}
        </TabsContent>
      ))}
    </Tabs>
  );
}

function getValueFromPath(path: string) {
  const match = TABS.find((tab) => path.startsWith(tab.href));
  return match ? match.value : "mirror";
}
