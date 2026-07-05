import { describe, it, expect } from "vitest";
import { buildAppleScript, escapeAppleString } from "../applescript";
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
    expect(script).toContain("set t to new tab with configuration cfg");
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

  it("split target creates a tab then splits right", () => {
    const script = buildAppleScript(p({ type: "shell", working_directory: "/x" }), "split");
    expect(script).toContain("set t to new tab with configuration cfg");
    expect(script).toContain("split t direction right with configuration cfg");
  });
});
