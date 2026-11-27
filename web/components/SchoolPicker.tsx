"use client";

import { useEffect } from "react";
import { CloseIcon } from "@/components/Icons";
import { usePrefs } from "@/components/Providers";
import SchoolGrid from "@/components/SchoolGrid";

export default function SchoolPicker() {
  const { pickerOpen, closePicker, setSchool, t } = usePrefs();

  useEffect(() => {
    if (!pickerOpen) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && closePicker();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [pickerOpen, closePicker]);

  if (!pickerOpen) return null;

  return (
    <div className="modal-backdrop" onClick={closePicker}>
      <div className="modal" role="dialog" aria-modal="true" aria-label={t("school.title")}
        onClick={(e) => e.stopPropagation()}>
        <div className="modal-head">
          <h2>{t("school.title")}</h2>
          <button type="button" className="icon-btn" onClick={closePicker} aria-label={t("school.close")}>
            <CloseIcon />
          </button>
        </div>
        <div className="school-list">
          <SchoolGrid autoFocus onPick={(s) => { setSchool(s.id); closePicker(); }} />
        </div>
      </div>
    </div>
  );
}
