import type { Profile } from "./types";

export type LaunchTarget = "tab" | "window" | "split";

/** Escape a string for safe interpolation into an AppleScript double-quoted literal. */
export function escapeAppleString(s: string): string {
  return s.replace(/\\/g, "\\\\").replace(/"/g, '\\"');
}

/**
 * Build a Ghostty AppleScript that opens the given profile.
 * `tab`: new tab in the frontmost window (falls back to a new window if none).
 * `window`: always a new window.
 * `split`: new tab, then split right (low-priority action).
 */
export function buildAppleScript(profile: Profile, target: LaunchTarget): string {
  const lines: string[] = [];
  lines.push("tell application \"Ghostty\"");
  lines.push("  set cfg to new surface configuration");

  if (profile.command && (profile.type === "ssh" || profile.type === "command")) {
    lines.push(`  set command of cfg to "${escapeAppleString(profile.command)}"`);
  } else if (profile.working_directory) {
    lines.push(
      `  set initial working directory of cfg to "${escapeAppleString(profile.working_directory)}"`
    );
  }

  if (target === "window") {
    lines.push("  set w to new window with configuration cfg");
  } else if (target === "split") {
    lines.push("  if (count of windows) > 0 then");
    lines.push("    set t to new tab with configuration cfg");
    lines.push("  else");
    lines.push("    set w to new window with configuration cfg");
    lines.push("  end if");
    lines.push("  split t direction right with configuration cfg");
  } else {
    lines.push("  if (count of windows) > 0 then");
    lines.push("    set t to new tab with configuration cfg");
    lines.push("  else");
    lines.push("    set w to new window with configuration cfg");
    lines.push("  end if");
  }
  lines.push("  activate");
  lines.push("end tell");
  return lines.join("\n");
}
