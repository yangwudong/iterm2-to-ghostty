import type { Profile } from "./types";

/** Render profiles in display-sort order (spec §4.1):
 *  ids in `order` first (in array order, first occurrence wins on dup),
 *  then remaining profiles alphabetically by name. */
export function sortByOrder(profiles: Profile[], order: string[]): Profile[] {
  const byId = new Map(profiles.map((p) => [p.id, p]));
  const seen = new Set<string>();
  const ordered: Profile[] = [];
  for (const id of order) {
    if (seen.has(id)) continue;
    const p = byId.get(id);
    if (p) {
      ordered.push(p);
      seen.add(id);
    }
  }
  const rest = profiles.filter((p) => !seen.has(p.id));
  rest.sort((a, b) => a.name.localeCompare(b.name));
  return [...ordered, ...rest];
}

function swap(order: string[], id: string, delta: -1 | 1): string[] {
  const i = order.indexOf(id);
  if (i < 0) return order;
  const j = i + delta;
  if (j < 0 || j >= order.length) return order;
  const next = order.slice();
  next[i] = order[j];
  next[j] = order[i];
  return next;
}

export function moveUp(order: string[], id: string): string[] {
  return swap(order, id, -1);
}

export function moveDown(order: string[], id: string): string[] {
  return swap(order, id, 1);
}

export function moveToTop(order: string[], id: string): string[] {
  const i = order.indexOf(id);
  if (i <= 0) return order;
  const next = order.slice();
  next.splice(i, 1);
  next.unshift(id);
  return next;
}

export function moveToBottom(order: string[], id: string): string[] {
  const i = order.indexOf(id);
  if (i < 0 || i === order.length - 1) return order;
  const next = order.slice();
  next.splice(i, 1);
  next.push(id);
  return next;
}

/** Return ids sorted alphabetically by profile name. */
export function resetOrder(profiles: Profile[]): string[] {
  return profiles.slice().sort((a, b) => a.name.localeCompare(b.name)).map((p) => p.id);
}

/** Filter profiles by a search query: whitespace tokens are AND-ed, each must
 *  match (case-insensitive substring) somewhere in name + command + tags.
 *  Preserves the input order. Empty query returns the input unchanged. */
export function filterProfiles(profiles: Profile[], query: string): Profile[] {
  const tokens = query.trim().toLowerCase().split(/\s+/).filter(Boolean);
  if (tokens.length === 0) return profiles;
  return profiles.filter((p) => {
    const hay = [p.name, p.command ?? "", ...p.tags].join(" ").toLowerCase();
    return tokens.every((t) => hay.includes(t));
  });
}
