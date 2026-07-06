import { describe, it, expect } from "vitest";
import { buildAppleScript, buildSyncAppleScript, escapeAppleString } from "../applescript";
import type { Profile } from "../types";

function p(over: Partial<Profile>): Profile {
  return {
    id: "x",
    name: "X",
    type: "shell",
    working_directory: null,
    command: null,
    tags: [],
    skip: false,
    raw: {},
    ...over,
  };
}

describe("escapeAppleString", () => {
  it("escapes backslashes and double quotes", () => {
    expect(escapeAppleString('a"b\\c')).toBe('a\\"b\\\\c');
  });
});

describe("buildAppleScript", () => {
  it("ssh in a new tab uses command of cfg", () => {
    const script = buildAppleScript(p({ type: "ssh", command: "ssh jack@host" }), "tab");
    expect(script).toContain('set command of cfg to "ssh jack@host"');
    // 'in window 1' is REQUIRED: a bare 'new tab' sent to the application errors
    // with -1708 "Can't continue new tab" (Ghostty still creates the tab as a
    // side effect, so it looks like it works, but osascript exits non-zero and
    // Raycast keeps the dialog open). Targeting window 1 exits cleanly.
    expect(script).toContain("set t to new tab with configuration cfg in window 1");
    expect(script).toContain("set w to new window with configuration cfg");
  });

  it("shell in a new tab sets initial working directory and no command", () => {
    const script = buildAppleScript(
      p({ type: "shell", working_directory: "/Users/jack/work/x" }),
      "tab"
    );
    expect(script).toContain('set initial working directory of cfg to "/Users/jack/work/x"');
    expect(script).not.toContain("set command of cfg");
  });

  it("new window target always uses new window", () => {
    const script = buildAppleScript(p({ type: "ssh", command: "ssh a@b" }), "window");
    expect(script).toContain("set w to new window with configuration cfg");
    expect(script).not.toContain("new tab");
  });

  it("escapes a quote inside the command", () => {
    const script = buildAppleScript(
      p({ type: "ssh", command: 'ssh jack@host -t "tmux a"' }),
      "tab"
    );
    expect(script).toContain('set command of cfg to "ssh jack@host -t \\"tmux a\\""');
  });

  it("split target splits the active terminal right, with new-window fallback", () => {
    const script = buildAppleScript(p({ type: "shell", working_directory: "/x" }), "split");
    expect(script).toContain("set t to terminal 1 of selected tab of window 1");
    expect(script).toContain("split t direction right with configuration cfg");
    expect(script).toContain("set w to new window with configuration cfg");
    // Must NOT create a new tab (that was the old buggy behavior).
    expect(script).not.toContain("new tab");
  });
});

describe("buildSyncAppleScript", () => {
  const SCRIPT = "/Users/jack/workspaces/iterm2-to-ghostty/iterm2_to_ghostty.py";

  it("tab target: runs zsh -lc python3 in a new tab, keeps surface open", () => {
    const script = buildSyncAppleScript(SCRIPT, "tab");
    expect(script).toContain('set command of cfg to "/bin/zsh -lc \\"python3');
    expect(script).toContain(`'${SCRIPT}'`);
    expect(script).toContain("--export-profiles-json");
    expect(script).toContain("set wait after command of cfg to true");
    expect(script).toContain("set t to new tab with configuration cfg");
    expect(script).toContain("set w to new window with configuration cfg");
  });

  it("window target: always new window, no tab", () => {
    const script = buildSyncAppleScript(SCRIPT, "window");
    expect(script).toContain("set w to new window with configuration cfg");
    expect(script).not.toContain("new tab");
  });

  it("escapes a double-quote in the script path", () => {
    const script = buildSyncAppleScript('/path/"weird".py', "tab");
    // The inner double-quotes must be backslash-escaped in the AppleScript literal.
    expect(script).toContain('\\"weird\\"');
  });

  it("single-quotes the path so spaces are tolerated", () => {
    const script = buildSyncAppleScript("/path with spaces/script.py", "tab");
    expect(script).toContain("'/path with spaces/script.py'");
  });

  it("shell-escapes a single-quote in the path (no breakout from the quoting)", () => {
    const script = buildSyncAppleScript("/path/to/it's.py", "tab");
    // The raw unescaped quote must NOT appear mid-path (it would close the
    // single-quoted segment and let the rest be interpreted by the shell).
    expect(script).not.toMatch(/it's\.py/);
    // The path tail is still present (escaping didn't drop it).
    expect(script).toContain("s.py");
  });
});
