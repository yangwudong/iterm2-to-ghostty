import { readFileSync } from "node:fs";
import type { Profile, ProfilesDocument } from "./types";

export class ProfilesError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "ProfilesError";
  }
}

/** Default location the Python export script writes to. */
export const DEFAULT_PROFILES_PATH =
  process.env.HOME + "/.config/ghostty/profiles.json";

export interface LoadedProfiles {
  profiles: Profile[];
  order: string[];
}

/** Load and validate profiles.json. Throws ProfilesError on any problem. */
export function loadProfiles(path: string = DEFAULT_PROFILES_PATH): LoadedProfiles {
  let raw: string;
  try {
    raw = readFileSync(path, "utf-8");
  } catch (err) {
    throw new ProfilesError(
      `Could not read ${path}. Run \`./iterm2_to_ghostty.py --export-profiles-json\` first. (${
        (err as NodeJS.ErrnoException).message
      })`
    );
  }

  let parsed: unknown;
  try {
    parsed = JSON.parse(raw);
  } catch (err) {
    throw new ProfilesError(
      `profiles.json is invalid JSON: ${(err as Error).message}`
    );
  }

  const doc = parsed as Partial<ProfilesDocument>;
  if (!doc || typeof doc !== "object" || doc.schema_version !== 1) {
    throw new ProfilesError(
      "profiles.json is missing schema_version: 1. Re-run the export script."
    );
  }
  if (!Array.isArray(doc.profiles)) {
    throw new ProfilesError("profiles.json has no profiles array.");
  }
  const order = Array.isArray(doc.order) ? doc.order.filter((x) => typeof x === "string") : [];
  return {
    profiles: doc.profiles.filter((p) => p && !p.skip) as Profile[],
    order: order as string[],
  };
}
