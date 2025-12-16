export {};

declare global {
  interface Window {
    bf: {
      checkVersions: (profilePath?: string) => Promise<{ local: string; remote: string; github: string; firefox: string }>;
      updateBetterfox: (payload: { profilePath: string }) => Promise<{ ok: boolean; log: string[]; version?: string }>;
      backupProfile: (payload: { profilePath: string; destPath: string; retentionDays?: number }) => Promise<{ ok: boolean; log: string[] }>;
      listProfiles: () => Promise<{ name: string; path: string }[]>;
      chooseDir: () => Promise<string | null>;
      openPath: (path: string) => Promise<boolean>;
      openUrl: (url: string) => Promise<boolean>;
    };
  }
}
