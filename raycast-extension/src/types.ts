export type ProfileType = "ssh" | "shell" | "command";

export interface Profile {
  id: string;
  name: string;
  type: ProfileType;
  working_directory: string | null;
  command: string | null;
  tags: string[];
  skip: boolean;
  raw: Record<string, unknown>;
}

export interface ProfilesDocument {
  schema_version: number;
  exported_at: string;
  source: string;
  order?: string[];
  profiles: Profile[];
}
