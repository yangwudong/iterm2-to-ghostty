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
  moveUp,
  moveDown,
  moveToTop,
  moveToBottom,
  resetOrder,
} from "./ordering";
import type { Profile } from "./types";
import { iconForType, subtitleFor } from "./index";

export default function Command() {
  const [{ profiles, order, error }, setState] = useState(() => {
    try {
      const loaded = loadProfiles();
      return {
        profiles: loaded.profiles,
        order: loaded.order,
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

  return (
    <List
      navigationTitle="Reorder iTerm Profiles"
      searchBarPlaceholder="Find a profile to move (clear search before bulk moves)"
    >
      {sorted.map((profile, index) => (
        <List.Item
          key={profile.id}
          id={profile.id}
          icon={iconForType(profile.type)}
          title={profile.name}
          subtitle={subtitleFor(profile)}
          accessories={[{ text: String(index + 1) }]}
          keywords={[profile.name, ...profile.tags]}
          actions={
            <ActionPanel>
              <Action
                title="Move Up"
                icon={Icon.ArrowUp}
                shortcut={{ modifiers: ["opt"], key: "arrowUp" }}
                onAction={() => apply(moveUp(order, profile.id))}
              />
              <Action
                title="Move Down"
                icon={Icon.ArrowDown}
                shortcut={{ modifiers: ["opt"], key: "arrowDown" }}
                onAction={() => apply(moveDown(order, profile.id))}
              />
              <Action
                title="Move to Top"
                icon={Icon.ChevronUp}
                shortcut={{ modifiers: ["opt", "cmd"], key: "arrowUp" }}
                onAction={() => apply(moveToTop(order, profile.id))}
              />
              <Action
                title="Move to Bottom"
                icon={Icon.ChevronDown}
                shortcut={{ modifiers: ["opt", "cmd"], key: "arrowDown" }}
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
