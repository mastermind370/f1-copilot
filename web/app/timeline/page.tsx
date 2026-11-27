"use client";

// Old URL from before the F-1 section moved under /f1. Kept so bookmarks keep working.
import { useRouter } from "next/navigation";
import { useEffect } from "react";

export default function Redirect() {
  const router = useRouter();
  useEffect(() => {
    router.replace(`/f1/timeline${window.location.search}`);
  }, [router]);
  return null;
}
