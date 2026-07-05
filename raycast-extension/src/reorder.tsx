import React, { useState, useCallback } from "react";
import {
  Action,
  ActionPanel,
  Icon,
  List,
  showToast,
  Toast,
} from "@raycast/api";
import {
  loadProfiles,
  saveProfilesOrder,
  DEFAULT_PROFILES_PATH,
  ProfilesError,
} from "./profiles";
import {
  sortByOrder,
  filterProfiles,
  moveUp,
  moveDown,
  moveToTop,
  moveToBottom,
  resetOrder,
} from "./ordering";
import type { Profile } from "./types";
import { iconForType, subtitleFor } from "./index";

export default function Command() {
  const [searchText, setSearchText] = useState("");
  const [{ profiles, order, error }, setState] = useState(() => {
    try {
      const loaded = loadProfiles();
      const order = loaded.order.length > 0 ? loaded.order : resetOrder(loaded.profiles);
      return {
        profiles: loaded.profiles,
        order,
        error: null as string | null,
      };
    } catch (err) {
      return {
        profiles: [] as Profile[],
        order: [] as string[],
        error: err instanceof ProfilesError ? err.message : (err as Error).message,
      };
    }
  });

  const apply = useCallback((nextOrder: string[]) => {
    setState((s) => ({ ...s, order: nextOrder }));
    try {
      saveProfilesOrder(DEFAULT_PROFILES_PATH, nextOrder);
    } catch (err) {
      showToast({
        style: Toast.Style.Failure,
        title: "Could not save order",
        message: (err as Error).message,
      });
    }
  }, []);

  if (error) {
    return (
      <List>
        <List.Item icon={Icon.ExclamationMark} title="No profiles loaded" subtitle={error} />
      </List>
    );
  }

  const sorted = sortByOrder(profiles, order);
  const globalIndex = new Map(sorted.map((p, i) => [p.id, i + 1]));
  const visible = filterProfiles(sorted, searchText);

  return (
    <List
      filtering={false}
      onSearchTextChange={setSearchText}
      navigationTitle="Reorder Ghostty Profiles"
      searchBarPlaceholder="Find a profile to move (clear search before bulk moves)"
    >
      {visible.map((profile) => (
        <List.Item
          key={profile.id}
          id={profile.id}
          icon={iconForType(profile.type)}
          title={profile.name}
          subtitle={subtitleFor(profile)}
          accessories={[{ text: String(globalIndex.get(profile.id) ?? 0) }]}
          actions={
            <ActionPanel>
              <Action
                title="Move Up"
                icon={Icon.ArrowUp}
                shortcut={{ modifiers: ["cmd"], key: "u" }}
                onAction={() => apply(moveUp(order, profile.id))}
              />
              <Action
                title="Move Down"
                icon={Icon.ArrowDown}
                shortcut={{ modifiers: ["cmd"], key: "d" }}
                onAction={() => apply(moveDown(order, profile.id))}
              />
              <Action
                title="Move to Top"
                icon={Icon.ChevronUp}
                shortcut={{ modifiers: ["opt", "cmd"], key: "u" }}
                onAction={() => apply(moveToTop(order, profile.id))}
              />
              <Action
                title="Move to Bottom"
                icon={Icon.ChevronDown}
                shortcut={{ modifiers: ["opt", "cmd"], key: "d" }}
                onAction={() => apply(moveToBottom(order, profile.id))}
              />
              <Action
                title="Reset to Alphabetical"
                icon={Icon.ArrowClockwise}
                shortcut={{ modifiers: ["cmd", "shift"], key: "r" }}
                onAction={() => apply(resetOrder(profiles))}
              />
            </ActionPanel>
          }
        />
      ))}
    </List>
  );
}
