import { describe, it, expect, beforeEach, afterEach } from "vitest";
import { writeFileSync, mkdirSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { loadProfiles, ProfilesError } from "../profiles";

const tmp = join(tmpdir(), "raycast-profiles-test");

beforeEach(() => {
  mkdirSync(tmp, { recursive: true });
});
afterEach(() => {
  rmSync(tmp, { recursive: true, force: true });
});

describe("loadProfiles", () => {
  it("returns the profiles array when the JSON is valid", () => {
    const path = join(tmp, "profiles.json");
    writeFileSync(
      path,
      JSON.stringify({
        schema_version: 1,
        exported_at: "2026-07-05T00:00:00Z",
        source: "com.googlecode.iterm2",
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
    const result = loadProfiles(path);
    expect(result).toHaveLength(1);
    expect(result[0].name).toBe("NAS");
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
