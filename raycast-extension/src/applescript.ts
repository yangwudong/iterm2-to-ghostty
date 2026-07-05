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
 * `split`: split the active terminal right (new-window fallback if none).
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
    lines.push("    set t to terminal 1 of selected tab of window 1");
    lines.push("    split t direction right with configuration cfg");
    lines.push("  else");
    lines.push("    set w to new window with configuration cfg");
    lines.push("  end if");
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

/**
 * Build a Ghostty AppleScript that opens a login shell and runs the iTerm2
 * export script, keeping the surface open so the user sees the result.
 *
 * Runs `/bin/zsh -lc "python3 '<scriptPath>' --export-profiles-json"` so the
 * user's full login PATH is in effect (python3 resolves as in their terminal).
 * `wait after command` keeps the tab open after the command exits.
 */
export function buildSyncAppleScript(scriptPath: string, target: LaunchTarget): string {
  // Shell-single-quote the path so spaces AND single-quotes are safe (a raw `'`
  // in the path would otherwise break out of the surrounding '...').
  const shSq = (s: string) => `'${s.replace(/'/g, "'\\''")}'`;
  const shellCommand = `/bin/zsh -lc "python3 ${shSq(scriptPath)} --export-profiles-json"`;
  const lines: string[] = [];
  lines.push("tell application \"Ghostty\"");
  lines.push("  set cfg to new surface configuration");
  lines.push(`  set command of cfg to "${escapeAppleString(shellCommand)}"`);
  lines.push("  set wait after command of cfg to true");
  if (target === "window") {
    lines.push("  set w to new window with configuration cfg");
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
