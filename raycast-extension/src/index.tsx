import React, { useState, useCallback } from "react";
import {
  Action,
  ActionPanel,
  Clipboard,
  Icon,
  List,
  showToast,
  Toast,
  getPreferenceValues,
  openCommandPreferences,
} from "@raycast/api";
import { execFile } from "node:child_process";
import { existsSync } from "node:fs";
import { loadProfiles, DEFAULT_PROFILES_PATH, ProfilesError } from "./profiles";
import { buildAppleScript, buildSyncAppleScript, LaunchTarget } from "./applescript";
import { sortByOrder, filterProfiles } from "./ordering";
import type { Profile } from "./types";

const SYNC_ID = "__sync__";
const SYNC_PSEUDO: Profile = {
  id: SYNC_ID,
  name: "*** Sync Profiles ***",
  type: "command",
  working_directory: null,
  command: null,
  tags: ["sync", "export", "iterm", "ghostty", "profiles"],
  skip: false,
  raw: {},
};

export function iconForType(type: Profile["type"]) {
  switch (type) {
    case "ssh":
      return Icon.Globe;
    case "command":
      return Icon.Gear;
    default:
      return Icon.Terminal;
  }
}

export function subtitleFor(profile: Profile): string {
  if (profile.command) return profile.command;
  if (profile.working_directory) return profile.working_directory;
  return "(default shell)";
}

/** Run the AppleScript via osascript. Shows a toast on failure. */
function runGhostty(script: string) {
  execFile("osascript", ["-e", script], (err) => {
    if (err) {
      showToast({
        style: Toast.Style.Failure,
        title: "Ghostty launch failed",
        message: err.message,
      });
    }
  });
}

function makeActions(profile: Profile) {
  const launch = (target: LaunchTarget) => () => runGhostty(buildAppleScript(profile, target));
  return (
    <ActionPanel>
      <Action title="Open in New Tab" icon={Icon.Plus} onAction={launch("tab")} />
      <Action
        title="Open in New Window"
        icon={Icon.Window}
        shortcut={{ modifiers: ["cmd"], key: "return" }}
        onAction={launch("window")}
      />
      <Action
        title="Open as Split Pane (Right)"
        icon={Icon.ArrowRight}
        onAction={launch("split")}
      />
      {profile.command ? (
        <Action
          title="Copy Command"
          icon={Icon.Clipboard}
          shortcut={{ modifiers: ["cmd", "shift"], key: "c" }}
          onAction={() => {
            Clipboard.copy(profile.command || "");
            showToast({ style: Toast.Style.Success, title: "Command copied" });
          }}
        />
      ) : null}
      {profile.working_directory ? (
        <Action.ShowInFinder
          title="Reveal Working Directory"
          icon={Icon.Folder}
          path={profile.working_directory}
        />
      ) : null}
    </ActionPanel>
  );
}

/** Trigger the iTerm2 export by opening Ghostty and running the script in a login shell. */
function syncNow(scriptPath: string) {
  if (!scriptPath) {
    showToast({
      style: Toast.Style.Failure,
      title: "No script path set",
      message: "Set iterm2_to_ghostty.py in command preferences",
    });
    openCommandPreferences();
    return;
  }
  runGhostty(buildSyncAppleScript(scriptPath, "tab"));
}

function makeSyncActions(scriptPath: string) {
  return (
    <ActionPanel>
      <Action title="Sync Now" icon={Icon.ArrowClockwise} onAction={() => syncNow(scriptPath)} />
    </ActionPanel>
  );
}

export default function Command() {
  const [searchText, setSearchText] = useState("");
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

  const refresh = useCallback(() => {
    try {
      const loaded = loadProfiles();
      setState({ profiles: loaded.profiles, order: loaded.order, error: null });
    } catch (err) {
      setState({
        profiles: [],
        order: [],
        error: err instanceof ProfilesError ? err.message : (err as Error).message,
      });
    }
  }, []);

  const fileExists = existsSync(DEFAULT_PROFILES_PATH);
  const scriptPath = (getPreferenceValues() as { scriptPath?: string }).scriptPath ?? "";
  const syncVisible = filterProfiles([SYNC_PSEUDO], searchText).length > 0;

  if (error) {
    return (
      <List>
        <List.Item
          icon={Icon.ExclamationMark}
          title="No profiles loaded"
          subtitle={error}
          accessories={fileExists ? [] : [{ text: "run the export script" }]}
          actions={
            <ActionPanel>
              <Action title="Refresh" icon={Icon.ArrowClockwise} onAction={refresh} />
            </ActionPanel>
          }
        />
      </List>
    );
  }

  if (profiles.length === 0) {
    return (
      <List>
        <List.Item
          icon={Icon.Document}
          title="No profiles exported yet"
          subtitle="Run: ./iterm2_to_ghostty.py --export-profiles-json"
          actions={
            <ActionPanel>
              <Action title="Refresh" icon={Icon.ArrowClockwise} onAction={refresh} />
            </ActionPanel>
          }
        />
      </List>
    );
  }

  return (
    <List
      filtering={false}
      onSearchTextChange={setSearchText}
      navigationTitle="Ghostty Profiles"
      searchBarPlaceholder="Search profiles by name, host, tag…"
      actions={
        <ActionPanel>
          <Action title="Refresh" icon={Icon.ArrowClockwise} onAction={refresh} />
        </ActionPanel>
      }
    >
      {filterProfiles(sortByOrder(profiles, order), searchText).map((profile) => (
        <List.Item
          key={profile.id}
          id={profile.id}
          icon={iconForType(profile.type)}
          title={profile.name}
          subtitle={subtitleFor(profile)}
          accessories={profile.tags.slice(0, 3).map((t) => ({ tag: t }))}
          actions={makeActions(profile)}
        />
      ))}
      {syncVisible ? (
        <List.Item
          key={SYNC_ID}
          id={SYNC_ID}
          icon={Icon.ArrowClockwise}
          title={SYNC_PSEUDO.name}
          subtitle="Re-export from iTerm2"
          actions={makeSyncActions(scriptPath)}
        />
      ) : null}
    </List>
  );
}
