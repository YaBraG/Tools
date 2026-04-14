# Release

Tools uses GitHub Releases as the distribution and update source.

## Release Checklist

1. Update `APP_VERSION` in `app/metadata.py`.
2. Confirm `pyproject.toml` still reads the version dynamically from the app.
3. Confirm bundled FFmpeg files and notices are present:

- `assets\ffmpeg\bin\ffmpeg.exe`
- `assets\ffmpeg\bin\ffprobe.exe`
- `assets\ffmpeg\README.txt`
- `assets\ffmpeg\LICENSE`
- `assets\ffmpeg\THIRD_PARTY_NOTICES.md`

4. Build the app and installer:

```powershell
.\scripts\build.ps1
```

5. Smoke test `dist\Tools\Tools.exe`.
6. Create and push a matching Git tag:

```powershell
git tag v0.3.0
git push origin v0.3.0
```

7. Create a GitHub Release for that tag.
8. Upload the installer from `dist\installer\Tools-Setup-v0.3.0.exe`.
9. Publish the release.

## Asset Naming

Use this installer asset naming convention:

```text
Tools-Setup-v0.3.0.exe
```

The updater looks for `.exe` release assets and prefers filenames containing
`setup` or `installer`.

## Optional GitHub CLI Flow

If GitHub CLI is installed and authenticated:

```powershell
gh release create v0.3.0 .\dist\installer\Tools-Setup-v0.3.0.exe --title "Tools v0.3.0" --notes "Audio Tools recording release."
```

The in-app updater reads the latest published full release from GitHub.

GitHub Releases API reference:
https://docs.github.com/en/rest/releases/releases#get-the-latest-release
