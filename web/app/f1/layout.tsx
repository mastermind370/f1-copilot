import type { ReactNode } from "react";
import F1Nav from "@/components/F1Nav";

// Everything that was the original F-1 Compliance Copilot lives under /f1.
export default function F1Layout({ children }: { children: ReactNode }) {
  return (
    <>
      <F1Nav />
      {children}
    </>
  );
}
