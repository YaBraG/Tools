from __future__ import annotations

import json
import re
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app.metadata import (
    APP_NAME,
    APP_VERSION,
    GITHUB_LATEST_RELEASE_API_URL,
    GITHUB_REPOSITORY,
    INSTALLER_ASSET_KEYWORDS,
    INSTALLER_ASSET_SUFFIXES,
)


class UpdateCheckError(RuntimeError):
    """Raised when GitHub release metadata cannot be checked."""


@dataclass(frozen=True)
class ReleaseAsset:
    name: str
    download_url: str
    size: int = 0


@dataclass(frozen=True)
class UpdateInfo:
    current_version: str
    latest_version: str
    release_url: str
    release_name: str
    installer_asset: ReleaseAsset | None
    release_notes: str = ""


class GitHubReleaseUpdateChecker:
    def __init__(
        self,
        current_version: str = APP_VERSION,
        latest_release_api_url: str = GITHUB_LATEST_RELEASE_API_URL,
        repository: str = GITHUB_REPOSITORY,
        timeout_seconds: int = 10,
    ) -> None:
        self.current_version = current_version
        self.latest_release_api_url = latest_release_api_url
        self.repository = repository
        self.timeout_seconds = timeout_seconds

    def check_for_update(self) -> UpdateInfo | None:
        release = self._fetch_latest_release()
        latest_version = self._normalize_version(
            str(release.get("tag_name") or release.get("name") or "")
        )

        if not latest_version:
            raise UpdateCheckError("The latest GitHub release does not include a version tag.")

        if not self._is_newer_version(latest_version, self.current_version):
            return None

        assets = self._parse_assets(release.get("assets", []))
        installer_asset = self._find_installer_asset(assets)

        return UpdateInfo(
            current_version=self.current_version,
            latest_version=latest_version,
            release_url=str(release.get("html_url") or ""),
            release_name=str(release.get("name") or release.get("tag_name") or ""),
            installer_asset=installer_asset,
            release_notes=str(release.get("body") or ""),
        )

    def _fetch_latest_release(self) -> dict:
        request = Request(
            self.latest_release_api_url,
            headers={
                "Accept": "application/vnd.github+json",
                "User-Agent": f"{APP_NAME}/{self.current_version}",
            },
        )

        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                payload = response.read().decode("utf-8")
        except HTTPError as error:
            if error.code == 404:
                raise UpdateCheckError(
                    "No published GitHub release was found for this app."
                ) from error
            raise UpdateCheckError(f"GitHub returned HTTP {error.code}.") from error
        except URLError as error:
            raise UpdateCheckError(f"Unable to reach GitHub: {error.reason}") from error
        except TimeoutError as error:
            raise UpdateCheckError("The update check timed out.") from error

        try:
            data = json.loads(payload)
        except json.JSONDecodeError as error:
            raise UpdateCheckError("GitHub returned an invalid release response.") from error

        if not isinstance(data, dict):
            raise UpdateCheckError("GitHub returned an unexpected release response.")

        return data

    @staticmethod
    def _parse_assets(raw_assets: object) -> list[ReleaseAsset]:
        if not isinstance(raw_assets, list):
            return []

        assets: list[ReleaseAsset] = []
        for raw_asset in raw_assets:
            if not isinstance(raw_asset, dict):
                continue

            name = str(raw_asset.get("name") or "")
            download_url = str(raw_asset.get("browser_download_url") or "")
            if not name or not download_url:
                continue

            size = raw_asset.get("size") or 0
            assets.append(
                ReleaseAsset(
                    name=name,
                    download_url=download_url,
                    size=int(size) if isinstance(size, int) else 0,
                )
            )

        return assets

    @staticmethod
    def _find_installer_asset(assets: list[ReleaseAsset]) -> ReleaseAsset | None:
        executable_assets = [
            asset
            for asset in assets
            if asset.name.lower().endswith(INSTALLER_ASSET_SUFFIXES)
        ]

        for asset in executable_assets:
            normalized_name = asset.name.lower()
            if any(keyword in normalized_name for keyword in INSTALLER_ASSET_KEYWORDS):
                return asset

        return executable_assets[0] if executable_assets else None

    @staticmethod
    def _normalize_version(version: str) -> str:
        return version.strip().lstrip("vV")

    @classmethod
    def _is_newer_version(cls, latest_version: str, current_version: str) -> bool:
        return cls._version_key(latest_version) > cls._version_key(current_version)

    @staticmethod
    def _version_key(version: str) -> tuple[int, int, int]:
        normalized = version.strip().lstrip("vV").split("+", 1)[0].split("-", 1)[0]
        parts = [int(part) for part in re.findall(r"\d+", normalized)]
        padded_parts = (parts + [0, 0, 0])[:3]
        return padded_parts[0], padded_parts[1], padded_parts[2]
