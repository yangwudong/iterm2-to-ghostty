import { describe, it, expect } from "vitest";
import {
  sortByOrder,
  moveUp,
  moveDown,
  moveToTop,
  moveToBottom,
  resetOrder,
  filterProfiles,
} from "../ordering";
import type { Profile } from "../types";

function profile(id: string, name: string = id): Profile {
  return {
    id,
    name,
    type: "shell",
    working_directory: null,
    command: null,
    tags: [],
    skip: false,
    raw: {},
  };
}

const P = [profile("a", "Alpha"), profile("b", "Beta"), profile("c", "Charlie")];

describe("sortByOrder", () => {
  it("empty order falls back to alphabetical by name", () => {
    expect(sortByOrder(P, []).map((p) => p.id)).toEqual(["a", "b", "c"]);
  });

  it("order covers all -> exact order", () => {
    expect(sortByOrder(P, ["c", "a", "b"]).map((p) => p.id)).toEqual(["c", "a", "b"]);
  });

  it("order covers some -> ordered first, rest alphabetical", () => {
    expect(sortByOrder(P, ["c"]).map((p) => p.id)).toEqual(["c", "a", "b"]);
  });

  it("duplicate ids in order -> first occurrence wins", () => {
    expect(sortByOrder(P, ["c", "c", "a"]).map((p) => p.id)).toEqual(["c", "a", "b"]);
  });

  it("id in order but missing from profiles -> skipped", () => {
    expect(sortByOrder(P, ["ghost", "b"]).map((p) => p.id)).toEqual(["b", "a", "c"]);
  });
});

describe("moveUp / moveDown", () => {
  it("moveUp swaps with predecessor", () => {
    expect(moveUp(["a", "b", "c"], "b")).toEqual(["b", "a", "c"]);
  });
  it("moveUp at top is a no-op", () => {
    expect(moveUp(["a", "b", "c"], "a")).toEqual(["a", "b", "c"]);
  });
  it("moveDown swaps with successor", () => {
    expect(moveDown(["a", "b", "c"], "b")).toEqual(["a", "c", "b"]);
  });
  it("moveDown at bottom is a no-op", () => {
    expect(moveDown(["a", "b", "c"], "c")).toEqual(["a", "b", "c"]);
  });
  it("moveUp/Down with missing id -> unchanged", () => {
    expect(moveUp(["a", "b"], "ghost")).toEqual(["a", "b"]);
    expect(moveDown(["a", "b"], "ghost")).toEqual(["a", "b"]);
  });
});

describe("moveToTop / moveToBottom", () => {
  it("moveToTop from middle", () => {
    expect(moveToTop(["a", "b", "c"], "c")).toEqual(["c", "a", "b"]);
  });
  it("moveToTop already first -> unchanged", () => {
    expect(moveToTop(["a", "b"], "a")).toEqual(["a", "b"]);
  });
  it("moveToBottom from middle", () => {
    expect(moveToBottom(["a", "b", "c"], "a")).toEqual(["b", "c", "a"]);
  });
  it("moveToBottom already last -> unchanged", () => {
    expect(moveToBottom(["a", "b"], "b")).toEqual(["a", "b"]);
  });
  it("missing id -> unchanged", () => {
    expect(moveToTop(["a"], "ghost")).toEqual(["a"]);
    expect(moveToBottom(["a"], "ghost")).toEqual(["a"]);
  });
});

describe("resetOrder", () => {
  it("returns ids sorted alphabetically by name", () => {
    const ps = [profile("z", "Zeta"), profile("a", "Alpha"), profile("m", "Mi")];
    expect(resetOrder(ps)).toEqual(["a", "m", "z"]);
  });
});

function fp(id: string, name: string, command: string | null, tags: string[]): Profile {
  return { id, name, type: "shell", working_directory: null, command, tags, skip: false, raw: {} };
}

const F = [
  fp("ub1", "Perficient PC Ubuntu", "ssh jack@ubuntu1.jyang.eu.org", ["perficient", "ubuntu1", "jack"]),
  fp("nas", "NAS", "ssh admin@nas.local", ["nas", "home", "admin"]),
  fp("becon-qa", "BeCon Micro China QA", null, ["becon", "china", "qa"]),
];

describe("filterProfiles", () => {
  it("empty query returns all, order preserved", () => {
    expect(filterProfiles(F, "").map((p) => p.id)).toEqual(["ub1", "nas", "becon-qa"]);
  });

  it("whitespace-only query returns all", () => {
    expect(filterProfiles(F, "   ").map((p) => p.id)).toEqual(["ub1", "nas", "becon-qa"]);
  });

  it("single token matches name (case-insensitive)", () => {
    expect(filterProfiles(F, "ubuntu").map((p) => p.id)).toEqual(["ub1"]);
  });

  it("single token matches a tag (e.g. ssh user 'jack')", () => {
    expect(filterProfiles(F, "jack").map((p) => p.id)).toEqual(["ub1"]);
  });

  it("multi-token AND: all tokens must match somewhere", () => {
    expect(filterProfiles(F, "becon qa").map((p) => p.id)).toEqual(["becon-qa"]);
  });

  it("multi-token AND excludes when only one token matches", () => {
    expect(filterProfiles(F, "becon nas").map((p) => p.id)).toEqual([]);
  });

  it("order is preserved across multiple matches", () => {
    // ub1 and nas both have 'ssh' in command; original order kept.
    expect(filterProfiles(F, "ssh").map((p) => p.id)).toEqual(["ub1", "nas"]);
  });

  it("no match returns empty array", () => {
    expect(filterProfiles(F, "zzz")).toEqual([]);
  });
});
