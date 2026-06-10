"""
Desktop pet — Nicole. Simple version, no QThread workers.
"""

import os
import subprocess as sp
import sys
import tempfile
import threading
import wave
from pathlib import Path

import requests
from PyQt6.QtCore import QTimer, Qt, QThread, pyqtSignal, QPointF
from PyQt6.QtGui import (
    QFont, QMouseEvent, QAction, QPainter, QColor, QBrush, QPen, QPixmap, QPolygonF,
)
from PyQt6.QtWidgets import (
    QApplication, QHBoxLayout, QLabel, QLineEdit, QMenu, QPushButton, QVBoxLayout, QWidget,
)

BACKEND = os.getenv("BACKEND_URL", "http://127.0.0.1:8000")


# ── Audio recorder ────────────────────────────────────────────────

class AudioRecorder(QThread):
    finished = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self._recording = False

    def run(self):
        import pyaudio
        self._frames = []
        pa = pyaudio.PyAudio()
        stream = pa.open(format=pyaudio.paInt16, channels=1, rate=16000,
                         input=True, frames_per_buffer=1024)
        self._recording = True
        print("[rec] started (pyaudio)")
        try:
            while self._recording:
                self._frames.append(stream.read(1024, exception_on_overflow=False))
        except Exception as e: print(f"[rec] {e}")
        stream.stop_stream(); stream.close(); pa.terminate()
        if self._frames:
            raw = b"".join(self._frames)
            print(f"[rec] done: {len(raw)} bytes")
            tmp = tempfile.mktemp(suffix=".wav", dir="/tmp")
            with wave.open(tmp, "wb") as wf:
                wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(16000)
                wf.writeframes(raw)
            self.finished.emit(tmp)

    def stop(self): self._recording = False


# ── Speech bubble ─────────────────────────────────────────────────

class SpeechBubble(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        l = QVBoxLayout(self); l.setContentsMargins(12,8,12,8)
        self._label = QLabel(); self._label.setWordWrap(True)
        self._label.setFont(QFont("PingFang SC", 12)); self._label.setStyleSheet("color:#1a1a1a")
        self._label.setMaximumWidth(260); l.addWidget(self._label)
        self._t = QTimer(self); self._t.setSingleShot(True); self._t.timeout.connect(self.hide)

    def show_text(self, text, anchor):
        self._label.setText(text); self.adjustSize()
        p = anchor.pos()
        x = p.x() + anchor.width() - self.width()//2
        y = p.y() - self.height() - 12
        self.move(max(0,x), max(0,y)); self.show(); self.raise_()
        self._t.start(15000)

    def hideEvent(self, e):
        # Force clear on hide to prevent ghost artifact
        super().hideEvent(e)
        self.update()

    def paintEvent(self, e):
        p = QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setBrush(QBrush(QColor(255,255,255,235))); p.setPen(QPen(QColor(200,200,220),1))
        r = self.rect().adjusted(1,1,-1,-1); p.drawRoundedRect(r,12,12)
        cx = self.width()//2; tri = QPolygonF()
        tri.append(QPointF(cx-6,r.bottom()+1)); tri.append(QPointF(cx+6,r.bottom()+1))
        tri.append(QPointF(cx,r.bottom()+9)); p.setPen(Qt.PenStyle.NoPen); p.drawPolygon(tri)


# ── Input bar ─────────────────────────────────────────────────────

class InputBar(QWidget):
    send_text = pyqtSignal(str)
    send_voice = pyqtSignal(str)
    recording_started = pyqtSignal()  # mic button pressed

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        l = QHBoxLayout(self); l.setContentsMargins(4,4,4,4); l.setSpacing(4)
        self._input = QLineEdit()
        self._input.setPlaceholderText("跟妮可说话..."); self._input.setFont(QFont("PingFang SC",12))
        self._input.setStyleSheet("QLineEdit{background:rgba(255,255,255,200);border-radius:8px;padding:4px 8px;color:#1a1a1a;}")
        self._input.returnPressed.connect(self._send)
        self._send_btn = QPushButton("↑"); self._send_btn.setFont(QFont("PingFang SC",14))
        self._send_btn.setFixedSize(30,30)
        self._send_btn.setStyleSheet("QPushButton{background:rgba(100,150,255,200);border-radius:15px;color:white;}QPushButton:hover{background:rgba(100,150,255,240);}QPushButton:disabled{background:rgba(180,180,180,180);}")
        self._send_btn.clicked.connect(self._send)
        self._mic_btn = QPushButton("🎤"); self._mic_btn.setCheckable(True)
        self._mic_btn.setFont(QFont("PingFang SC",14)); self._mic_btn.setFixedSize(30,30)
        self._mic_btn.setStyleSheet("QPushButton{background:rgba(255,255,255,200);border-radius:15px;}QPushButton:checked{background:rgba(255,80,80,200);}QPushButton:disabled{background:rgba(180,180,180,180);}")
        self._mic_btn.toggled.connect(self._mic)
        l.addWidget(self._input); l.addWidget(self._send_btn); l.addWidget(self._mic_btn)
        self._rec = None; self._thinking = False

    def lock(self):
        self._thinking = True
        self._input.setEnabled(False); self._send_btn.setEnabled(False); self._mic_btn.setEnabled(False)
        self._input.setPlaceholderText("尼可思考中..."); self._input.clear()
        self.show(); self.raise_()

    def unlock(self):
        self._thinking = False
        self._input.setEnabled(True); self._send_btn.setEnabled(True); self._mic_btn.setEnabled(True)
        self._input.setPlaceholderText("跟妮可说话...")

    def _send(self):
        if self._thinking: return
        t = self._input.text().strip()
        if t: self.send_text.emit(t); self._input.clear()

    def _mic(self, checked):
        if self._thinking: self._mic_btn.setChecked(False); return
        if checked:
            self.recording_started.emit()
            self._mic_btn.setText("⏺"); self._rec = AudioRecorder()
            self._rec.finished.connect(lambda p: self.send_voice.emit(p))
            self._rec.finished.connect(lambda _: self._mic_btn.setChecked(False))
            self._rec.finished.connect(lambda _: self._mic_btn.setText("🎤"))
            self._rec.start()
        else:
            self._mic_btn.setText("🎤")
            if self._rec: self._rec.stop()


# ── Pet window ────────────────────────────────────────────────────

class PetWindow(QWidget):
    _thinking_done = pyqtSignal()

    def __init__(self, frames_dir=None, fps=24, scale=1.0):
        super().__init__()
        self._scale = scale; self._fps = fps; self._idx = 0
        root = Path(__file__).resolve().parent.parent
        self._frames_root = frames_dir or str(root / "resources" / "frames")
        # States: normal → question → thinking → answering → normal
        #   normal:    idle loop
        #   question:  transition, play once
        #   thinking:  loop while waiting for LLM
        #   answering: transition, play once → auto back to normal
        self._frames = {}
        self._state = "normal"
        self._load_all_states()
        if not self._frames.get("normal"): raise FileNotFoundError(f"No frames in {self._frames_root}/normal/")
        print(f"[pet] frames: " + ", ".join(f"{k}:{len(v)}" for k, v in self._frames.items()))

        self._pet_label = QLabel(self)
        self._pet_label.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        layout = QVBoxLayout(self); layout.setContentsMargins(0,0,0,0); layout.addWidget(self._pet_label)

        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WidgetAttribute.WA_MacAlwaysShowToolWindow)

        self._drag_pos = None; self._thinking = False
        self._current_player = None; self._current_tts_stream = None; self._cancelled = False
        self._update()
        normal_frames = self._frames["normal"]
        w = normal_frames[0].width(); h = normal_frames[0].height()
        self.setFixedSize(w, h)

        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._menu)

        self._bubble = SpeechBubble()
        self._bar = InputBar()
        self._bar.send_text.connect(self._on_text)
        self._bar.send_voice.connect(self._on_voice)
        self._bar.recording_started.connect(self._cancel_current)
        self._thinking_done.connect(lambda: QTimer.singleShot(2000, self._think_off))
        self._bar.hide()

        t = QTimer(self); t.timeout.connect(self._tick); t.start(int(1000/fps))
        print(f"[pet] {w}x{h} @ {fps}fps")

    def _load_all_states(self):
        for state in ("normal", "question", "thinking", "answering"):
            d = os.path.join(self._frames_root, state)
            if not os.path.isdir(d):
                continue
            frames = []
            for f in sorted(os.listdir(d)):
                if f.endswith(".png"):
                    pix = QPixmap(os.path.join(d, f))
                    if not pix.isNull():
                        if self._scale != 1.0:
                            pix = pix.scaled(int(pix.width()*self._scale), int(pix.height()*self._scale),
                                             Qt.AspectRatioMode.KeepAspectRatio,
                                             Qt.TransformationMode.SmoothTransformation)
                        frames.append(pix)
            if frames:
                self._frames[state] = frames

    def _update(self):
        frames = self._frames.get(self._state, self._frames.get("normal", []))
        if not frames:
            return
        pix = frames[self._idx % len(frames)]
        self._pet_label.clear()
        self._pet_label.setPixmap(pix)
        self._pet_label.update()
        self.update()

    def _tick(self):
        frames = self._frames.get(self._state, [])
        if not frames:
            return
        self._idx += 1
        if self._state == "question" and self._idx >= len(frames):
            self._idx = 0
            self._state = "thinking"
        elif self._state in ("normal", "thinking", "answering"):
            self._idx = self._idx % len(frames)
        self._update()

    # ── state ──────────────────────────────────────────────────

    def _think_on(self):
        self._thinking = True
        # question → thinking (or straight to thinking if no question frames)
        if self._frames.get("question"):
            self._state = "question"
        else:
            self._state = "thinking"
        self._idx = 0
        self._update(); self._bar.lock()

    def _think_off(self):
        self._thinking = False
        if self._frames.get("answering"):
            self._state = "answering"
            self._idx = 0
            # Auto back to normal after answering animation
            QTimer.singleShot(5000, self._to_normal)
        else:
            self._state = "normal"
        self._update(); self._bar.unlock()

    def _to_normal(self):
        if not self._thinking:
            self._state = "normal"; self._idx = 0; self._update()

    # ── input ──────────────────────────────────────────────────

    def _on_text(self, text):
        self._cancel_current()
        self._think_on()
        threading.Thread(target=self._do_text, args=(text,), daemon=True).start()

    def _on_voice(self, path):
        self._cancel_current()
        self._think_on()
        threading.Thread(target=self._do_voice, args=(path,), daemon=True).start()

    def _cancel_current(self):
        """Kill audio, close TTS stream, mark cancelled."""
        self._cancelled = True
        if self._current_player:
            try: self._current_player.kill()
            except: pass
            self._current_player = None
        if self._current_tts_stream:
            try: self._current_tts_stream.close()
            except: pass
            self._current_tts_stream = None

    # ── worker functions (run in thread) ───────────────────────

    def _do_text(self, text):
        self._cancelled = False
        print(f"[pet] INPUT: {text!r}")
        try:
            resp = requests.post(f"{BACKEND}/api/v1/chat",
                                 json={"message": text, "include_context": False}, timeout=30)
            reply = resp.json().get("content", "")
            print(f"[pet] {reply}")
            # Show bubble
            QTimer.singleShot(0, lambda r=reply: self._bubble.show_text(r, self))
            # TTS streaming: play each file as it arrives
            self._current_tts_stream = requests.post(f"{BACKEND}/api/v1/voice/tts",
                data={"text": reply}, timeout=120, stream=True)
            resp2 = self._current_tts_stream
            if resp2.status_code == 200 and not self._cancelled:
                first = True
                for line in resp2.iter_lines():
                    if self._cancelled: break
                    if not line: continue
                    import json as _json
                    f = _json.loads(line).get("file")
                    if f:
                        print(f"[pet] playing {f}")
                        if first:
                            self._thinking_done.emit()
                            first = False
                        self._play_file(f)
                        try: os.unlink(f)
                        except OSError: pass
            else:
                print(f"[pet] TTS failed: HTTP {resp2.status_code}")
                QTimer.singleShot(0, self._think_off)
        except Exception as e:
            print(f"[pet] err: {e}")
            QTimer.singleShot(0, self._think_off)

    def _do_voice(self, path):
        self._cancelled = False
        try:
            with open(path, "rb") as f:
                resp = requests.post(f"{BACKEND}/api/v1/voice/chat",
                                     files={"file": f}, timeout=30)
            if resp.status_code == 200:
                reply = resp.json().get("content", "")
                print(f"[pet] voice reply: {reply}")
                QTimer.singleShot(0, lambda r=reply: self._bubble.show_text(r, self))
                # TTS streaming
                self._current_tts_stream = requests.post(f"{BACKEND}/api/v1/voice/tts",
                    data={"text": reply}, timeout=120, stream=True)
                resp2 = self._current_tts_stream
                if resp2.status_code == 200 and not self._cancelled:
                    first = True
                    for line in resp2.iter_lines():
                        if self._cancelled: break
                        if not line: continue
                        import json as _json
                        f = _json.loads(line).get("file")
                        if f:
                            f = os.path.abspath(f)
                            print(f"[pet] playing {f}")
                            if first:
                                QTimer.singleShot(0, self._think_off)
                                first = False
                            self._play_file(f)
                            try: os.unlink(f)
                            except OSError: pass
                else:
                    print(f"[pet] voice TTS failed: HTTP {resp2.status_code}")
                    QTimer.singleShot(0, self._think_off)
        except Exception as e:
            print(f"[pet] voice err: {e}")
            QTimer.singleShot(0, self._think_off)
        finally:
            try: os.unlink(path)
            except OSError: pass

    def _play_file(self, path: str):
        """Play WAV, blocking. Can be killed by _cancel_current."""
        try:
            self._current_player = sp.Popen(["afplay", path])
            self._current_player.wait()
            self._current_player = None
        except Exception as e:
            print(f"[pet] play err: {e}")

    # ── hover ──────────────────────────────────────────────────

    def enterEvent(self, e): self._show_bar()
    def leaveEvent(self, e): QTimer.singleShot(500, self._hide_bar)
    def _show_bar(self):
        self._bar.move(self.pos().x(), self.pos().y() + self.height() + 4)
        self._bar.resize(self.width() + 60, 38); self._bar.show(); self._bar.raise_()
    def _hide_bar(self):
        if self._bar._thinking: return
        if not self.underMouse() and not self._bar.underMouse(): self._bar.hide()

    # ── drag ───────────────────────────────────────────────────

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton: self._drag_pos = e.globalPosition()
    def mouseMoveEvent(self, e):
        if self._drag_pos is not None:
            d = e.globalPosition() - self._drag_pos
            self.move(int(self.pos().x()+d.x()), int(self.pos().y()+d.y()))
            self._drag_pos = e.globalPosition()
            if self._bar.isVisible(): self._show_bar()
    def mouseReleaseEvent(self, e): self._drag_pos = None

    def _menu(self, pos):
        m = QMenu(self); m.addAction("退出妮可", QApplication.quit); m.exec(self.mapToGlobal(pos))
