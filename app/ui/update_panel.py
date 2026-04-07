from __future__ import annotations

from PySide6.QtCore import QThread, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
)

from app.core.updater import GitHubReleaseUpdateChecker, UpdateInfo
from app.metadata import APP_VERSION, GITHUB_RELEASES_URL


class UpdateCheckWorker(QThread):
    result_ready = Signal(object)
    error = Signal(str)

    def run(self) -> None:
        try:
            result = GitHubReleaseUpdateChecker().check_for_update()
            self.result_ready.emit(result)
        except Exception as error:
            self.error.emit(str(error))


class UpdatePanel(QFrame):
    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("infoPanel")
        self.update_info: UpdateInfo | None = None
        self.worker: UpdateCheckWorker | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 22, 24, 22)
        layout.setSpacing(12)

        title = QLabel("Updates")
        title.setObjectName("panelTitle")

        self.status_label = QLabel(
            "Check GitHub Releases for a newer installer when you are ready."
        )
        self.status_label.setObjectName("panelBody")
        self.status_label.setWordWrap(True)

        self.version_label = QLabel(f"Current version: {APP_VERSION}")
        self.version_label.setObjectName("mutedLabel")

        button_row = QHBoxLayout()
        button_row.setSpacing(10)

        self.check_button = QPushButton("Check for updates")
        self.check_button.setObjectName("primaryButton")
        self.check_button.clicked.connect(self.check_for_updates)

        self.download_button = QPushButton("Download update")
        self.download_button.setObjectName("secondaryButton")
        self.download_button.clicked.connect(self.open_update_download)
        self.download_button.hide()

        self.release_button = QPushButton("Open releases")
        self.release_button.setObjectName("secondaryButton")
        self.release_button.clicked.connect(
            lambda: QDesktopServices.openUrl(QUrl(GITHUB_RELEASES_URL))
        )

        button_row.addWidget(self.check_button)
        button_row.addWidget(self.download_button)
        button_row.addWidget(self.release_button)
        button_row.addStretch(1)

        layout.addWidget(title)
        layout.addWidget(self.status_label)
        layout.addWidget(self.version_label)
        layout.addLayout(button_row)

    def check_for_updates(self) -> None:
        if self.worker is not None:
            return

        self.update_info = None
        self.download_button.hide()
        self.check_button.setEnabled(False)
        self.status_label.setText("Checking GitHub Releases...")

        self.worker = UpdateCheckWorker()
        self.worker.result_ready.connect(self._handle_update_result)
        self.worker.error.connect(self._handle_update_error)
        self.worker.finished.connect(self._cleanup_worker)
        self.worker.start()

    def open_update_download(self) -> None:
        if self.update_info is None:
            return

        asset = self.update_info.installer_asset
        url = asset.download_url if asset is not None else self.update_info.release_url
        if url:
            QDesktopServices.openUrl(QUrl(url))

    def _handle_update_result(self, update_info: UpdateInfo | None) -> None:
        if update_info is None:
            self.status_label.setText("You are running the latest published version.")
            self.version_label.setText(f"Current version: {APP_VERSION}")
            return

        self.update_info = update_info
        asset_message = (
            f"Installer: {update_info.installer_asset.name}"
            if update_info.installer_asset is not None
            else "No installer asset was found; opening the release page is recommended."
        )
        self.status_label.setText(
            "A newer version is available. Download the installer, close Tools, "
            "then run the installer to update.\n\n"
            f"{asset_message}"
        )
        self.version_label.setText(
            f"Current version: {update_info.current_version} | "
            f"Latest version: {update_info.latest_version}"
        )
        self.download_button.show()

    def _handle_update_error(self, message: str) -> None:
        self.status_label.setText(f"Unable to check for updates. {message}")
        self.version_label.setText(f"Current version: {APP_VERSION}")

    def _cleanup_worker(self) -> None:
        if self.worker is not None:
            self.worker.deleteLater()
            self.worker = None
        self.check_button.setEnabled(True)

