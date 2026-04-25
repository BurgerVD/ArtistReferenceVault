import os
from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QRubberBand, QFileDialog, QPushButton, QWidget, QSlider, QStackedWidget
from PyQt6.QtCore import Qt, QUrl, QTimer, QRect, QSize
from PyQt6.QtGui import QPixmap, QImage, QKeySequence, QShortcut, QMovie
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
from PyQt6.QtMultimediaWidgets import QVideoWidget
from PIL import Image

class AdvancedLightbox(QDialog):
    def __init__(self, parent_grid, starting_item, parent=None):
        super().__init__(parent)
        self.main_window = parent #save reference to access the moodboard safely
        self.grid = parent_grid
        self.current_index = self.grid.row(starting_item)
        
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setModal(True)
        self.setStyleSheet("background-color: rgba(15, 15, 18, 0.98); color: white;")
        self.showMaximized()
        
        self.is_grayscale = False
        self.is_mirrored = False
        self.original_qimage = None
        self.FRAME_STEP_MS = 41 
        
        self.setup_ui()
        self.rubber_band = QRubberBand(QRubberBand.Shape.Rectangle, self.image_label)
        self.load_media()
        self.setup_hotkeys()

    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        
        #Top Bar 
        top_bar = QHBoxLayout()
        top_bar.addStretch()
        close_btn = QPushButton("✕")
        close_btn.setFixedSize(40, 40)
        close_btn.setStyleSheet("""
            QPushButton { background-color: transparent; font-size: 20px; font-weight: bold; border-radius: 20px; }
            QPushButton:hover { background-color: #e74c3c; }
        """)
        close_btn.clicked.connect(self.accept)
        top_bar.addWidget(close_btn)
        main_layout.addLayout(top_bar)
        
        #Center Content
        center_layout = QHBoxLayout()
        arrow_style = """
            QPushButton { background-color: rgba(255,255,255,0.05); border: none; font-size: 24px; border-radius: 10px; }
            QPushButton:hover { background-color: rgba(255,255,255,0.2); }
        """
        self.prev_btn = QPushButton("◀")
        self.prev_btn.setFixedSize(50, 100)
        self.prev_btn.setStyleSheet(arrow_style)
        self.prev_btn.clicked.connect(self.show_previous)
        
        self.next_btn = QPushButton("▶")
        self.next_btn.setFixedSize(50, 100)
        self.next_btn.setStyleSheet(arrow_style)
        self.next_btn.clicked.connect(self.show_next)
        
        self.media_stack = QStackedWidget()
        
        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.media_stack.addWidget(self.image_label)
        
        self.video_widget = QVideoWidget()
        self.media_player = QMediaPlayer()
        self.audio_output = QAudioOutput()
        self.media_player.setAudioOutput(self.audio_output)
        self.media_player.setVideoOutput(self.video_widget)
        self.media_stack.addWidget(self.video_widget)
        
        center_layout.addWidget(self.prev_btn)
        center_layout.addWidget(self.media_stack, stretch=1)
        center_layout.addWidget(self.next_btn)
        
        main_layout.addLayout(center_layout)
        
        #Video Controls
        self.video_controls = QHBoxLayout()
        self.play_btn = QPushButton("⏸")
        self.play_btn.setFixedSize(40, 40)
        self.play_btn.setStyleSheet("background-color: #3498db; border-radius: 20px; font-size: 16px;")
        self.play_btn.clicked.connect(self.toggle_playback)
        
        self.video_slider = QSlider(Qt.Orientation.Horizontal)
        self.video_slider.setStyleSheet("""
            QSlider::groove:horizontal { border: 1px solid #333; height: 8px; background: #2a2a2a; border-radius: 4px; }
            QSlider::handle:horizontal { background: #3498db; width: 14px; margin: -3px 0; border-radius: 7px; }
        """)
        self.video_slider.sliderMoved.connect(self.set_video_position)
        
        self.time_label = QLabel("00:00 / 00:00")
        
        self.video_controls.addWidget(self.play_btn)
        self.video_controls.addWidget(self.video_slider)
        self.video_controls.addWidget(self.time_label)
        
        self.video_container = QWidget()
        self.video_container.setLayout(self.video_controls)
        self.video_container.hide() 
        main_layout.addWidget(self.video_container)

        #Bottom Bar 
        self.bottom_bar = QHBoxLayout()
        self.palette_container = QHBoxLayout()
        
        tool_label = QLabel("Hotkeys: [V] Gray | [M] Mirror | [,] [.] Scrub | [Space] Play | [Shift + Drag] Crop")
        tool_label.setStyleSheet("color: #7f8c8d; font-size: 14px;")
        
        #Added Pin to Moodboard button
        self.pin_btn = QPushButton("📌 Pin to Moodboard")
        self.pin_btn.setStyleSheet("""
            QPushButton { background-color: #9b59b6; color: white; border-radius: 4px; padding: 5px 15px; font-weight: bold; border: none; }
            QPushButton:hover { background-color: #8e44ad; }
        """)
        self.pin_btn.clicked.connect(self.send_to_moodboard)
        
        self.bottom_bar.addWidget(tool_label)
        self.bottom_bar.addStretch()
        self.bottom_bar.addWidget(self.pin_btn)
        self.bottom_bar.addSpacing(15)
        self.bottom_bar.addLayout(self.palette_container)
        
        main_layout.addLayout(self.bottom_bar)
        
        self.media_player.positionChanged.connect(self.update_slider)
        self.media_player.durationChanged.connect(self.update_duration)

    # Feature: Send to Moodboard
    def send_to_moodboard(self):
        # Access the master app safely and push the image to the board
        if hasattr(self, 'main_window') and self.main_window and hasattr(self.main_window, 'moodboard'):
            self.main_window.moodboard.board.add_image(self.current_path)
            self.main_window.moodboard.show()
            
            # Temporary visual feedback
            self.pin_btn.setText("✅ Pinned!")
            self.pin_btn.setStyleSheet("""
                QPushButton { background-color: #2ecc71; color: white; border-radius: 4px; padding: 5px 15px; font-weight: bold; border: none; }
            """)
            QTimer.singleShot(1500, self.reset_pin_btn)

    def reset_pin_btn(self):
        self.pin_btn.setText("📌 Pin to Moodboard")
        self.pin_btn.setStyleSheet("""
            QPushButton { background-color: #9b59b6; color: white; border-radius: 4px; padding: 5px 15px; font-weight: bold; border: none; }
            QPushButton:hover { background-color: #8e44ad; }
        """)

    def load_media(self):
        self.media_player.stop()
        if hasattr(self, 'movie') and self.movie:
            self.movie.stop()
            
        self.is_grayscale = False
        self.is_mirrored = False
        
        item = self.grid.item(self.current_index)
        if not item: return
        
        self.current_path = item.data(Qt.ItemDataRole.UserRole)
        ext = os.path.splitext(self.current_path)[1].lower()
        
        video_exts = ['.mp4', '.webm', '.avi', '.mkv']
        
        if ext in video_exts:
            self.media_stack.setCurrentWidget(self.video_widget)
            self.video_container.show()
            self.media_player.setSource(QUrl.fromLocalFile(self.current_path))
            self.media_player.play()
            self.play_btn.setText("⏸")
            self.clear_palette() 
            
        elif ext == '.gif':
            self.media_stack.setCurrentWidget(self.image_label)
            self.video_container.hide()
            self.movie = QMovie(self.current_path)
            self.image_label.setMovie(self.movie)
            self.movie.start()
            self.clear_palette()
            
        else:
            self.media_stack.setCurrentWidget(self.image_label)
            self.video_container.hide()
            self.original_qimage = QImage(self.current_path)
            self.apply_image_transformations()
            self.extract_and_display_palette()
            
        self.update_arrow_states()

    #Video & Frame Scrubbing Logic
    def toggle_playback(self):
        if self.media_player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.media_player.pause()
            self.play_btn.setText("▶")
        else:
            self.media_player.play()
            self.play_btn.setText("⏸")

    def step_frame_forward(self):
        if self.media_stack.currentWidget() == self.video_widget:
            self.media_player.pause()
            self.play_btn.setText("▶")
            new_pos = min(self.media_player.position() + self.FRAME_STEP_MS, self.media_player.duration())
            self.media_player.setPosition(new_pos)

    def step_frame_backward(self):
        if self.media_stack.currentWidget() == self.video_widget:
            self.media_player.pause()
            self.play_btn.setText("▶")
            new_pos = max(self.media_player.position() - self.FRAME_STEP_MS, 0)
            self.media_player.setPosition(new_pos)

    def update_slider(self, position):
        self.video_slider.setValue(position)
        self.update_time_label(position, self.media_player.duration())

    def update_duration(self, duration):
        self.video_slider.setRange(0, duration)
        self.update_time_label(self.media_player.position(), duration)

    def set_video_position(self, position):
        self.media_player.setPosition(position)

    def update_time_label(self, current, total):
        def format_time(ms):
            s = (ms // 1000) % 60
            m = (ms // 60000) % 60
            return f"{m:02d}:{s:02d}"
        self.time_label.setText(f"{format_time(current)} / {format_time(total)}")

    #Interaction & Hotkeys 
    def setup_hotkeys(self):
        QShortcut(QKeySequence("Left"), self).activated.connect(self.show_previous)
        QShortcut(QKeySequence("Right"), self).activated.connect(self.show_next)
        QShortcut(QKeySequence("V"), self).activated.connect(self.toggle_grayscale)
        QShortcut(QKeySequence("M"), self).activated.connect(self.toggle_mirror)
        QShortcut(QKeySequence("Space"), self).activated.connect(self.toggle_playback)
        QShortcut(QKeySequence("."), self).activated.connect(self.step_frame_forward)
        QShortcut(QKeySequence(","), self).activated.connect(self.step_frame_backward)

    def apply_image_transformations(self):
        if not self.original_qimage or self.media_stack.currentWidget() == self.video_widget: 
            return
        
        img = self.original_qimage.copy()
        if self.is_grayscale:
            img = img.convertToFormat(QImage.Format.Format_Grayscale8)
        if self.is_mirrored:
            img = img.mirrored(horizontal=True, vertical=False)
            
        pixmap = QPixmap.fromImage(img)
        target_width = max(500, self.width() - 150)
        target_height = max(500, self.height() - 150)
        
        scaled_pixmap = pixmap.scaled(
            target_width,
            target_height,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )
        self.image_label.setPixmap(scaled_pixmap)

    def toggle_grayscale(self):
        self.is_grayscale = not self.is_grayscale
        self.apply_image_transformations()

    def toggle_mirror(self):
        self.is_mirrored = not self.is_mirrored
        self.apply_image_transformations()

    def show_previous(self):
        if self.current_index > 0:
            self.current_index -= 1
            self.load_media()

    def show_next(self):
        if self.current_index < self.grid.count() - 1:
            self.current_index += 1
            self.load_media()

    def update_arrow_states(self):
        self.prev_btn.setEnabled(self.current_index > 0)
        self.next_btn.setEnabled(self.current_index < self.grid.count() - 1)
        
    def clear_palette(self):
        for i in reversed(range(self.palette_container.count())): 
            widget = self.palette_container.itemAt(i).widget() # type: ignore
            if widget: widget.deleteLater()

    def extract_and_display_palette(self):
        self.clear_palette()
        try:
            with Image.open(self.current_path) as img:
                img = img.convert('RGB')
                img.thumbnail((150, 150)) 
                quantized = img.quantize(colors=5, method=Image.Quantize.MEDIANCUT)
                palette = quantized.getpalette()[:15] #type:ignore
                hex_colors = [f"#{palette[i]:02x}{palette[i+1]:02x}{palette[i+2]:02x}" for i in range(0, 15, 3)]
                unique_colors = list(dict.fromkeys(hex_colors))
                
                for color in unique_colors:
                    btn = QPushButton()
                    btn.setFixedSize(30, 30)
                    btn.setToolTip(f"Click to copy {color}")
                    btn.setStyleSheet(f"background-color: {color}; border: 1px solid #333; border-radius: 15px;")
                    btn.clicked.connect(lambda checked, c=color: self.copy_to_clipboard(c))
                    self.palette_container.addWidget(btn)
        except Exception as e:
            print(f"Palette extraction failed: {e}")

    def copy_to_clipboard(self, text):
        from PyQt6.QtWidgets import QApplication
        QApplication.clipboard().setText(text) #type:ignore
        
    def closeEvent(self, event): #type:ignore
        self.media_player.stop()
        super().closeEvent(event)
        
    def mousePressEvent(self, event): #type:ignore
        if event is None: return
        has_shift = bool(event.modifiers() & Qt.KeyboardModifier.ShiftModifier)
        if self.media_stack.currentWidget() == self.image_label and event.button() == Qt.MouseButton.LeftButton and has_shift:
            self.crop_origin = event.position().toPoint()
            local_pos = self.image_label.mapFrom(self, self.crop_origin)
            self.rubber_band.setGeometry(QRect(local_pos, QSize()))
            self.rubber_band.show()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event): #type:ignore
        if self.rubber_band.isVisible() and event is not None:
            local_pos = self.image_label.mapFrom(self, event.position().toPoint())
            self.rubber_band.setGeometry(QRect(self.image_label.mapFrom(self, self.crop_origin), local_pos).normalized())

    def mouseReleaseEvent(self, event): #type:ignore
        if self.rubber_band.isVisible():
            if self.rubber_band.rect().width() > 20 and self.rubber_band.rect().height() > 20:
                self.save_cropped_region()
            self.rubber_band.hide()

    def save_cropped_region(self):
        pixmap = self.image_label.pixmap()
        if not pixmap: return
        
        crop_rect = self.rubber_band.geometry()
        cropped_pixmap = pixmap.copy(crop_rect)
        
        save_path, _ = QFileDialog.getSaveFileName(self, "Save Detail Crop", os.path.dirname(self.current_path), "Images (*.png *.jpg)")
        if save_path:
            cropped_pixmap.save(save_path)
            print(f"Detail crop saved to {save_path}")