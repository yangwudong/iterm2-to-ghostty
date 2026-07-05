import { describe, it, expect, beforeEach, afterEach } from "vitest";
import { writeFileSync, mkdirSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { loadProfiles, saveProfilesOrder, ProfilesError } from "../profiles";

const tmp = join(tmpdir(), "raycast-profiles-test");

beforeEach(() => {
  mkdirSync(tmp, { recursive: true });
});
afterEach(() => {
  rmSync(tmp, { recursive: true, force: true });
});

describe("loadProfiles", () => {
  it("returns profiles and order when the JSON is valid", () => {
    const path = join(tmp, "profiles.json");
    writeFileSync(
      path,
      JSON.stringify({
        schema_version: 1,
        exported_at: "2026-07-05T00:00:00Z",
        source: "com.googlecode.iterm2",
        order: ["nas", "other"],
        profiles: [
          {
            id: "nas",
            name: "NAS",
            type: "ssh",
            working_directory: null,
            command: "ssh admin@nas.local",
            tags: ["nas", "home"],
            skip: false,
            raw: {},
          },
        ],
      })
    );
    const { profiles, order } = loadProfiles(path);
    expect(profiles).toHaveLength(1);
    expect(profiles[0].name).toBe("NAS");
    expect(order).toEqual(["nas", "other"]);
  });

  it("returns empty order when the field is absent (backward compat)", () => {
    const path = join(tmp, "legacy.json");
    writeFileSync(
      path,
      JSON.stringify({
        schema_version: 1,
        exported_at: "2026-07-05T00:00:00Z",
        source: "com.googlecode.iterm2",
        profiles: [],
      })
    );
    const { order } = loadProfiles(path);
    expect(order).toEqual([]);
  });

  it("throws ProfilesError when the file is missing", () => {
    expect(() => loadProfiles(join(tmp, "nope.json"))).toThrow(ProfilesError);
  });

  it("throws ProfilesError when JSON is malformed", () => {
    const path = join(tmp, "bad.json");
    writeFileSync(path, "{ not json");
    expect(() => loadProfiles(path)).toThrow(ProfilesError);
  });

  it("throws ProfilesError when schema_version is absent", () => {
    const path = join(tmp, "noschema.json");
    writeFileSync(path, JSON.stringify({ profiles: [] }));
    expect(() => loadProfiles(path)).toThrow(ProfilesError);
  });
});

describe("saveProfilesOrder", () => {
  it("replaces only the order field, preserving profiles and other fields", () => {
    const path = join(tmp, "profiles.json");
    const original = {
      schema_version: 1,
      exported_at: "2026-07-05T00:00:00Z",
      source: "com.googlecode.iterm2",
      order: ["a", "b"],
      profiles: [
        { id: "a", name: "A", type: "ssh", working_directory: null, command: "ssh a@b", tags: ["a"], skip: false, raw: {} },
        { id: "b", name: "B", type: "shell", working_directory: "/x", command: null, tags: ["b"], skip: false, raw: {} },
      ],
    };
    writeFileSync(path, JSON.stringify(original, null, 2));

    saveProfilesOrder(path, ["b", "a"]);

    const reread = JSON.parse(require("fs").readFileSync(path, "utf-8"));
    expect(reread.order).toEqual(["b", "a"]);
    // profiles untouched (data-integrity contract).
    expect(reread.profiles).toEqual(original.profiles);
    expect(reread.source).toBe("com.googlecode.iterm2");
    expect(reread.schema_version).toBe(1);
  });
});
