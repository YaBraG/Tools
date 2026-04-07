# Update System

Tools uses a simple release-based update flow:

1. The user opens Settings.
2. The user clicks **Check for updates**.
3. The app calls the GitHub Releases latest-release API.
4. The app compares the release tag to the local `APP_VERSION`.
5. If a newer version exists, the app shows the current version, latest
   version, and a **Download update** button.
6. The button opens the installer asset from the GitHub Release.
7. The user closes Tools and runs the downloaded installer.

This avoids risky in-place binary patching and keeps the update flow easy to
debug.

## Source

The update checker uses:

```text
https://api.github.com/repos/YaBraG/Tools/releases/latest
```

The release page is:

```text
https://github.com/YaBraG/Tools/releases
```

GitHub's latest-release endpoint returns the latest published full release,
which excludes draft and prerelease releases.

GitHub API reference: https://docs.github.com/en/rest/releases/releases#get-the-latest-release

## Installer Asset Selection

When a newer release is found, the updater checks release assets and prefers:

- `.exe` assets containing `setup`
- `.exe` assets containing `installer`
- any `.exe` asset

If no installer asset is found, the app still opens the release page so the
user can choose the correct download manually.

## Limitations

- The update checker assumes the GitHub repository or release metadata is
  publicly accessible.
- The app does not download patches or modify its own installed files.
- The app does not silently install updates.
- The app does not currently check for updates on startup.
