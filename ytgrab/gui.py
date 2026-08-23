"""PySide6 desktop interface for ytgrab."""

import sys
import urllib.request
from pathlib import Path

from PySide6.QtCore import Qt, QThread, Signal, QUrl, QPoint
from PySide6.QtGui import QPixmap, QDesktopServices, QIcon, QPainter, QColor, QPolygon
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QLineEdit, QPushButton, QComboBox, QCheckBox, QProgressBar,
    QRadioButton, QButtonGroup, QStackedWidget, QFileDialog, QFrame,
    QGroupBox, QMessageBox,
)

from . import core, __version__


# yt-dlp reports postprocessor names with the "FFmpeg" prefix stripped.
STAGE_LABELS = {
    "ExtractAudio": "Extracting audio",
    "Merger": "Merging video and audio",
    "VideoRemuxer": "Remuxing",
    "VideoConvertor": "Converting",
    "EmbedThumbnail": "Embedding cover art",
    "Metadata": "Writing metadata",
    "MoveFiles": "Finishing up",
}


class Cancelled(Exception):
    """Raised inside a yt-dlp hook to abort a download."""


# --------------------------------------------------------------------------
# workers
# --------------------------------------------------------------------------

class InfoWorker(QThread):
    finished_ok = Signal(dict)
    failed = Signal(str)

    def __init__(self, url):
        super().__init__()
        self.url = url

    def run(self):
        try:
            self.finished_ok.emit(core.fetch_info(self.url))
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(core.clean_error(exc))


class ThumbWorker(QThread):
    loaded = Signal(bytes)

    def __init__(self, url):
        super().__init__()
        self.url = url

    def run(self):
        try:
            req = urllib.request.Request(self.url, headers={"User-Agent": "ytgrab"})
            with urllib.request.urlopen(req, timeout=15) as resp:
                self.loaded.emit(resp.read())
        except Exception:  # noqa: BLE001 - a missing thumbnail is not an error
            pass


class DownloadWorker(QThread):
    progress = Signal(dict)
    stage = Signal(str)
    finished_ok = Signal(str)
    failed = Signal(str)
    cancelled = Signal()

    def __init__(self, url, dest, mode, quality, container, embed):
        super().__init__()
        self.url, self.dest = url, dest
        self.mode, self.quality = mode, quality
        self.container, self.embed = container, embed
        self._cancel = False

    def cancel(self):
        self._cancel = True

    def _on_progress(self, d):
        if self._cancel:
            raise Cancelled()
        if d.get("status") == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
            done = d.get("downloaded_bytes") or 0
            self.progress.emit({
                "percent": (done / total * 100) if total else 0,
                "downloaded": done,
                "total": total,
                "speed": d.get("speed") or 0,
                "eta": d.get("eta") or 0,
            })
        elif d.get("status") == "finished":
            self.stage.emit("Processing")

    def _on_postprocess(self, d):
        if self._cancel:
            raise Cancelled()
        if d.get("status") == "started":
            self.stage.emit(STAGE_LABELS.get(d.get("postprocessor") or "", "Processing"))

    def run(self):
        try:
            path = core.download(
                self.url, self.dest, self.mode, self.quality,
                self.container, self.embed,
                progress_hook=self._on_progress,
                postprocessor_hook=self._on_postprocess,
            )
            self.finished_ok.emit(str(path))
        except Cancelled:
            self.cancelled.emit()
        except Exception as exc:  # noqa: BLE001
            if self._cancel:
                self.cancelled.emit()
            else:
                self.failed.emit(core.clean_error(exc))


# --------------------------------------------------------------------------
# main window
# --------------------------------------------------------------------------

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"ytgrab {__version__}")
        self.setMinimumWidth(620)
        self.dest_dir = core.default_download_dir()
        self.info_worker = None
        self.thumb_worker = None
        self.dl_worker = None
        self.last_file = None

        root = QWidget()
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(14)

        layout.addWidget(self._build_url_row())
        layout.addWidget(self._build_info_panel())
        layout.addWidget(self._build_mode_box())
        layout.addWidget(self._build_options())
        layout.addWidget(self._build_dest_row())
        layout.addWidget(self._build_actions())
        layout.addWidget(self._build_progress())
        layout.addStretch(1)

        self.statusBar().showMessage(self._ffmpeg_status())
        self._sync_mode()

    # -- construction ------------------------------------------------------

    def _build_url_row(self):
        box = QWidget()
        row = QHBoxLayout(box)
        row.setContentsMargins(0, 0, 0, 0)

        self.url_edit = QLineEdit()
        self.url_edit.setPlaceholderText("https://www.youtube.com/watch?v=...")
        self.url_edit.setClearButtonEnabled(True)
        self.url_edit.returnPressed.connect(self.fetch_info)
        self.url_edit.textChanged.connect(self._on_url_changed)

        self.fetch_btn = QPushButton("Fetch")
        self.fetch_btn.clicked.connect(self.fetch_info)

        paste_btn = QPushButton("Paste")
        paste_btn.setToolTip("Paste a link from the clipboard and read its details")
        paste_btn.clicked.connect(self.paste_and_fetch)

        row.addWidget(QLabel("Link:"))
        row.addWidget(self.url_edit, 1)
        row.addWidget(paste_btn)
        row.addWidget(self.fetch_btn)
        return box

    def _build_info_panel(self):
        self.info_panel = QFrame()
        self.info_panel.setFrameShape(QFrame.StyledPanel)
        self.info_panel.setVisible(False)
        row = QHBoxLayout(self.info_panel)

        self.thumb_label = QLabel()
        self.thumb_label.setFixedSize(160, 90)
        self.thumb_label.setScaledContents(True)
        self.thumb_label.setAlignment(Qt.AlignCenter)

        text_col = QVBoxLayout()
        self.title_label = QLabel()
        self.title_label.setWordWrap(True)
        font = self.title_label.font()
        font.setBold(True)
        self.title_label.setFont(font)
        self.meta_label = QLabel()
        self.meta_label.setStyleSheet("color: palette(mid);")
        text_col.addWidget(self.title_label)
        text_col.addWidget(self.meta_label)
        text_col.addStretch(1)

        row.addWidget(self.thumb_label)
        row.addLayout(text_col, 1)
        return self.info_panel

    def _build_mode_box(self):
        box = QGroupBox("What do you want?")
        row = QHBoxLayout(box)
        self.mode_group = QButtonGroup(self)

        specs = [
            ("video", "Video", "Video and audio together, muxed without re-encoding"),
            ("audio", "Audio (original)", "The audio stream exactly as YouTube stores it - no quality loss"),
            ("mp3", "MP3", "The audio converted to MP3 (a second lossy step)"),
        ]
        self.mode_buttons = {}
        for i, (key, label, tip) in enumerate(specs):
            btn = QRadioButton(label)
            btn.setToolTip(tip)
            btn.setChecked(key == "video")
            self.mode_group.addButton(btn, i)
            self.mode_buttons[key] = btn
            btn.toggled.connect(self._sync_mode)
            row.addWidget(btn)
        return box

    def _build_options(self):
        self.opt_stack = QStackedWidget()

        # video
        video = QWidget()
        g = QGridLayout(video)
        g.setContentsMargins(0, 0, 0, 0)
        self.res_combo = QComboBox()
        self.res_combo.addItem("Best available", "best")
        self.container_combo = QComboBox()
        self.container_combo.addItem("MP4 - plays everywhere", "mp4")
        self.container_combo.addItem("MKV - keeps the highest-quality streams as-is", "mkv")
        self.container_combo.setToolTip(
            "YouTube serves 4K only as VP9/AV1, which MP4 can't always hold.\n"
            "Choose MKV if you want maximum quality."
        )
        g.addWidget(QLabel("Resolution:"), 0, 0)
        g.addWidget(self.res_combo, 0, 1)
        g.addWidget(QLabel("Container:"), 1, 0)
        g.addWidget(self.container_combo, 1, 1)
        g.setColumnStretch(1, 1)
        self.opt_stack.addWidget(video)

        # audio
        audio = QWidget()
        g = QGridLayout(audio)
        g.setContentsMargins(0, 0, 0, 0)
        self.acodec_combo = QComboBox()
        self.acodec_combo.addItem("Best available (no re-encoding)", "best")
        self.acodec_combo.addItem("Prefer Opus (.opus)", "opus")
        self.acodec_combo.addItem("Prefer AAC (.m4a)", "m4a")
        g.addWidget(QLabel("Stream:"), 0, 0)
        g.addWidget(self.acodec_combo, 0, 1)
        g.setColumnStretch(1, 1)
        self.opt_stack.addWidget(audio)

        # mp3
        mp3 = QWidget()
        g = QGridLayout(mp3)
        g.setContentsMargins(0, 0, 0, 0)
        self.bitrate_combo = QComboBox()
        for label, value in [
            ("VBR V0 - best quality (~245 kbps)", "0"),
            ("320 kbps CBR", "320"),
            ("256 kbps CBR", "256"),
            ("192 kbps CBR", "192"),
            ("128 kbps CBR", "128"),
        ]:
            self.bitrate_combo.addItem(label, value)
        self.bitrate_combo.setCurrentIndex(3)
        g.addWidget(QLabel("Bitrate:"), 0, 0)
        g.addWidget(self.bitrate_combo, 0, 1)
        g.setColumnStretch(1, 1)
        self.opt_stack.addWidget(mp3)

        wrapper = QWidget()
        col = QVBoxLayout(wrapper)
        col.setContentsMargins(0, 0, 0, 0)
        col.addWidget(self.opt_stack)
        self.embed_check = QCheckBox("Embed cover art and metadata")
        self.embed_check.setChecked(True)
        col.addWidget(self.embed_check)
        return wrapper

    def _build_dest_row(self):
        box = QWidget()
        row = QHBoxLayout(box)
        row.setContentsMargins(0, 0, 0, 0)
        self.dest_edit = QLineEdit(str(self.dest_dir))
        self.dest_edit.setReadOnly(True)
        browse = QPushButton("Change...")
        browse.clicked.connect(self.choose_dest)
        row.addWidget(QLabel("Save to:"))
        row.addWidget(self.dest_edit, 1)
        row.addWidget(browse)
        return box

    def _build_actions(self):
        box = QWidget()
        row = QHBoxLayout(box)
        row.setContentsMargins(0, 0, 0, 0)
        self.download_btn = QPushButton("Download")
        self.download_btn.setMinimumHeight(38)
        self.download_btn.setDefault(True)
        self.download_btn.clicked.connect(self.start_download)
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setMinimumHeight(38)
        self.cancel_btn.setVisible(False)
        self.cancel_btn.clicked.connect(self.cancel_download)
        row.addWidget(self.download_btn, 1)
        row.addWidget(self.cancel_btn)
        return box

    def _build_progress(self):
        self.progress_panel = QWidget()
        col = QVBoxLayout(self.progress_panel)
        col.setContentsMargins(0, 0, 0, 0)

        top = QHBoxLayout()
        self.state_label = QLabel("")
        self.stats_label = QLabel("")
        self.stats_label.setStyleSheet("color: palette(mid);")
        self.stats_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        top.addWidget(self.state_label)
        top.addStretch(1)
        top.addWidget(self.stats_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setMaximumHeight(10)

        self.open_btn = QPushButton("Show in folder")
        self.open_btn.setVisible(False)
        self.open_btn.clicked.connect(self.open_dest)

        col.addLayout(top)
        col.addWidget(self.progress_bar)
        col.addWidget(self.open_btn)
        self.progress_panel.setVisible(False)
        return self.progress_panel

    # -- behaviour ---------------------------------------------------------

    def _ffmpeg_status(self):
        loc = core.ffmpeg_location()
        return f"ffmpeg: {loc}" if loc else "ffmpeg not found - conversion will fail"

    def current_mode(self):
        for key, btn in self.mode_buttons.items():
            if btn.isChecked():
                return key
        return "video"

    def _sync_mode(self):
        mode = self.current_mode()
        self.opt_stack.setCurrentIndex({"video": 0, "audio": 1, "mp3": 2}[mode])
        self.embed_check.setVisible(mode in ("audio", "mp3"))

    def _on_url_changed(self):
        # A new link invalidates whatever metadata is on screen.
        if self.info_panel.isVisible():
            self.info_panel.setVisible(False)
            self.res_combo.clear()
            self.res_combo.addItem("Best available", "best")

    def paste_and_fetch(self):
        text = QApplication.clipboard().text().strip()
        if text:
            self.url_edit.setText(text)
            self.fetch_info()

    def fetch_info(self):
        url = self.url_edit.text().strip()
        if not core.is_supported_url(url):
            self.statusBar().showMessage("Enter a valid http(s) link.", 5000)
            return
        if self.info_worker and self.info_worker.isRunning():
            return

        self.fetch_btn.setEnabled(False)
        self.fetch_btn.setText("Reading...")
        self.statusBar().showMessage("Reading video details...")

        self.info_worker = InfoWorker(url)
        self.info_worker.finished_ok.connect(self._on_info)
        self.info_worker.failed.connect(self._on_info_failed)
        self.info_worker.finished.connect(self._reset_fetch_btn)
        self.info_worker.start()

    def _reset_fetch_btn(self):
        self.fetch_btn.setEnabled(True)
        self.fetch_btn.setText("Fetch")

    def _on_info(self, info):
        self.title_label.setText(info["title"])
        bits = [b for b in (info["uploader"],
                            core.format_duration(info["duration"]),
                            "LIVE" if info["is_live"] else "") if b]
        self.meta_label.setText("  ·  ".join(bits))

        self.res_combo.clear()
        self.res_combo.addItem("Best available", "best")
        for h in info["heights"]:
            self.res_combo.addItem(f"{h}p", str(h))

        self.thumb_label.clear()
        if info["thumbnail"]:
            self.thumb_worker = ThumbWorker(info["thumbnail"])
            self.thumb_worker.loaded.connect(self._on_thumb)
            self.thumb_worker.start()

        self.info_panel.setVisible(True)
        self.statusBar().showMessage("Ready.", 4000)

    def _on_thumb(self, data):
        pix = QPixmap()
        if pix.loadFromData(data):
            self.thumb_label.setPixmap(pix)

    def _on_info_failed(self, message):
        self.info_panel.setVisible(False)
        self.statusBar().showMessage("Could not read that link.", 6000)
        QMessageBox.warning(self, "Could not read that link", message)

    def choose_dest(self):
        chosen = QFileDialog.getExistingDirectory(self, "Save downloads to", str(self.dest_dir))
        if chosen:
            self.dest_dir = Path(chosen)
            self.dest_edit.setText(chosen)

    def open_dest(self):
        target = self.last_file.parent if self.last_file else self.dest_dir
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(target)))

    def start_download(self):
        url = self.url_edit.text().strip()
        if not core.is_supported_url(url):
            QMessageBox.warning(self, "No link", "Paste a video link first.")
            return
        if not core.ffmpeg_location():
            QMessageBox.critical(
                self, "ffmpeg missing",
                "ffmpeg could not be found, so merging and conversion cannot run.",
            )
            return

        mode = self.current_mode()
        quality = {
            "video": lambda: self.res_combo.currentData(),
            "audio": lambda: self.acodec_combo.currentData(),
            "mp3": lambda: self.bitrate_combo.currentData(),
        }[mode]()

        self.download_btn.setVisible(False)
        self.cancel_btn.setVisible(True)
        self.progress_panel.setVisible(True)
        self.open_btn.setVisible(False)
        self.progress_bar.setRange(0, 0)  # indeterminate until bytes arrive
        self.state_label.setText("Starting...")
        self.stats_label.setText("")

        self.dl_worker = DownloadWorker(
            url, self.dest_dir, mode, quality,
            self.container_combo.currentData(), self.embed_check.isChecked(),
        )
        self.dl_worker.progress.connect(self._on_progress)
        self.dl_worker.stage.connect(self._on_stage)
        self.dl_worker.finished_ok.connect(self._on_done)
        self.dl_worker.failed.connect(self._on_failed)
        self.dl_worker.cancelled.connect(self._on_cancelled)
        self.dl_worker.start()

    def cancel_download(self):
        if self.dl_worker and self.dl_worker.isRunning():
            self.cancel_btn.setEnabled(False)
            self.state_label.setText("Cancelling...")
            self.dl_worker.cancel()

    def _on_progress(self, p):
        if p["total"]:
            self.progress_bar.setRange(0, 100)
            self.progress_bar.setValue(int(p["percent"]))
            self.state_label.setText(f"Downloading  {p['percent']:.1f}%")
        else:
            self.progress_bar.setRange(0, 0)
            self.state_label.setText("Downloading")
        bits = []
        if p["total"]:
            bits.append(f"{core.format_size(p['downloaded'])} / {core.format_size(p['total'])}")
        if p["speed"]:
            bits.append(f"{core.format_size(p['speed'])}/s")
        if p["eta"]:
            bits.append(f"{core.format_duration(p['eta'])} left")
        self.stats_label.setText("   ·   ".join(bits))

    def _on_stage(self, stage):
        self.progress_bar.setRange(0, 0)
        self.state_label.setText(stage + "...")
        self.stats_label.setText("")

    def _finish_ui(self):
        self.download_btn.setVisible(True)
        self.cancel_btn.setVisible(False)
        self.cancel_btn.setEnabled(True)

    def _on_done(self, path):
        self.last_file = Path(path)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(100)
        self.state_label.setText("Saved")
        size = self.last_file.stat().st_size if self.last_file.exists() else 0
        self.stats_label.setText(f"{self.last_file.name}   ·   {core.format_size(size)}")
        self.open_btn.setVisible(True)
        self.statusBar().showMessage(f"Saved to {self.last_file}", 8000)
        self._finish_ui()

    def _on_failed(self, message):
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.state_label.setText("Failed")
        self.stats_label.setText("")
        self._finish_ui()
        QMessageBox.critical(self, "Download failed", message)

    def _on_cancelled(self):
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.state_label.setText("Cancelled")
        self.stats_label.setText("")
        self._finish_ui()

    def closeEvent(self, event):
        if self.dl_worker and self.dl_worker.isRunning():
            self.dl_worker.cancel()
            self.dl_worker.wait(3000)
        event.accept()


def make_icon():
    """A small red-on-transparent play badge, so there is no binary asset to ship."""
    pix = QPixmap(64, 64)
    pix.fill(QColor(0, 0, 0, 0))
    p = QPainter(pix)
    p.setRenderHint(QPainter.Antialiasing)
    p.setBrush(QColor("#ff4b4b"))
    p.setPen(Qt.NoPen)
    p.drawRoundedRect(4, 12, 56, 40, 10, 10)
    p.setBrush(QColor("#ffffff"))
    p.drawPolygon(QPolygon([QPoint(26, 20), QPoint(26, 44), QPoint(44, 32)]))
    p.end()
    return QIcon(pix)


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("ytgrab")
    app.setApplicationDisplayName("ytgrab")
    app.setWindowIcon(make_icon())
    win = MainWindow()
    win.show()
    sys.exit(app.exec())
