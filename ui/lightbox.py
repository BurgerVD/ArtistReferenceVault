import os
from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QRubberBand, QFileDialog, QPushButton, QWidget, QSlider, QStackedWidget, QGraphicsView, QGraphicsScene, QGraphicsPixmapItem
from PyQt6.QtCore import Qt, QUrl, QTimer, QRect, QSize, QPointF
from PyQt6.QtGui import QPixmap, QImage, QKeySequence, QShortcut, QMovie, QPainter
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
from PyQt6.QtMultimediaWidgets import QVideoWidget
from PIL import Image

#Custom Camera View for Full-Resolution Lightbox Zooming
class LightboxImageView(QGraphicsView):
    def __init__(self, parent_lightbox):
        super().__init__()
        self.parent_lightbox = parent_lightbox
        self.image_scene = QGraphicsScene(self)
        self.setScene(self.image_scene)
        self.pixmap_item = QGraphicsPixmapItem()
        self.image_scene.addItem(self.pixmap_item)
        
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        self.setDragMode(QGraphicsView.DragMode.NoDrag)
        self.setStyleSheet("background: transparent; border: none;")
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        
        self._is_panning = False
        self._pan_start = QPointF()

    def update_image(self, pixmap):
        self.pixmap_item.setPixmap(pixmap)
        self.image_scene.setSceneRect(self.pixmap_item.boundingRect())
        self.fitInView(self.image_scene.itemsBoundingRect(), Qt.AspectRatioMode.KeepAspectRatio)

    def wheelEvent(self, event): # type: ignore
        if event is None: return
        zoom_in = 1.15
        zoom_out = 1.0 / zoom_in
        zoom = zoom_in if event.angleDelta().y() > 0 else zoom_out
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.scale(zoom, zoom)

    def mousePressEvent(self, event): # type: ignore
        if event is None: return
        has_shift = bool(event.modifiers() & Qt.KeyboardModifier.ShiftModifier)
        
        #Pass to crop tool if shift is held
        if has_shift and event.button() == Qt.MouseButton.LeftButton:
            self.parent_lightbox.start_crop(event.position().toPoint())
            event.accept()
            return
            
        if event.button() == Qt.MouseButton.MiddleButton or event.button() == Qt.MouseButton.LeftButton:
            self._is_panning = True
            self._pan_start = event.position()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event): # type: ignore
        if event is None: return
        if self.parent_lightbox.rubber_band.isVisible():
            self.parent_lightbox.update_crop(event.position().toPoint())
            event.accept()
            return
            
        if self._is_panning:
            delta = event.position() - self._pan_start
            self._pan_start = event.position()
            h_bar, v_bar = self.horizontalScrollBar(), self.verticalScrollBar()
            if h_bar and v_bar:
                h_bar.setValue(int(h_bar.value() - delta.x()))
                v_bar.setValue(int(v_bar.value() - delta.y()))
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event): # type: ignore
        if event is None: return
        if self.parent_lightbox.rubber_band.isVisible():
            self.parent_lightbox.finish_crop()
            event.accept()
            return
            
        if self._is_panning:
            self._is_panning = False
            self.setCursor(Qt.CursorShape.ArrowCursor)
            event.accept()
            return
        super().mouseReleaseEvent(event)

class AdvancedLightbox(QDialog):
    def __init__(self, parent_grid, starting_item, parent=None):
        super().__init__(parent)
        self.main_window = parent
        self.grid = parent_grid
        self.current_index = self.grid.row(starting_item)
        
        #Removed self.setModal(True) to allow dual-monitor interaction
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setStyleSheet("background-color: rgba(15, 15, 18, 0.98); color: white;")
        self.showMaximized()
        
        self.is_grayscale = False
        self.is_mirrored = False
        self.original_qimage = None
        self.FRAME_STEP_MS = 41 
        
        self.setup_ui()
        self.rubber_band = QRubberBand(QRubberBand.Shape.Rectangle, self.image_view)
        self.load_media()
        self.setup_hotkeys()

    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        
        top_bar = QHBoxLayout()
        top_bar.addStretch()
        close_btn = QPushButton("✕")
        close_btn.setFixedSize(40, 40)
        close_btn.setStyleSheet("QPushButton { background-color: transparent; font-size: 20px; font-weight: bold; border-radius: 20px; } QPushButton:hover { background-color: #e74c3c; }")
        close_btn.clicked.connect(self.accept)
        top_bar.addWidget(close_btn)
        main_layout.addLayout(top_bar)
        
        center_layout = QHBoxLayout()
        arrow_style = "QPushButton { background-color: rgba(255,255,255,0.05); border: none; font-size: 24px; border-radius: 10px; } QPushButton:hover { background-color: rgba(255,255,255,0.2); }"
        
        self.prev_btn = QPushButton("◀")
        self.prev_btn.setFixedSize(50, 100)
        self.prev_btn.setStyleSheet(arrow_style)
        self.prev_btn.clicked.connect(self.show_previous)
        
        self.next_btn = QPushButton("▶")
        self.next_btn.setFixedSize(50, 100)
        self.next_btn.setStyleSheet(arrow_style)
        self.next_btn.clicked.connect(self.show_next)
        
        self.media_stack = QStackedWidget()
        
        #Use QGraphicsView Camera instead of standard QLabel
        self.image_view = LightboxImageView(self)
        self.media_stack.addWidget(self.image_view)
        
        self.video_widget = QVideoWidget()
        self.media_player = QMediaPlayer()
        self.audio_output = QAudioOutput()
        self.media_player.setAudioOutput(self.audio_output)
        self.media_player.setVideoOutput(self.video_widget)
        self.media_stack.addWidget(self.video_widget)
        
        #Fallback label for GIFs
        self.gif_label = QLabel()
        self.gif_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.media_stack.addWidget(self.gif_label)
        
        center_layout.addWidget(self.prev_btn)
        center_layout.addWidget(self.media_stack, stretch=1)
        center_layout.addWidget(self.next_btn)
        
        main_layout.addLayout(center_layout)
        
        self.video_controls = QHBoxLayout()
        self.play_btn = QPushButton("⏸")
        self.play_btn.setFixedSize(40, 40)
        self.play_btn.setStyleSheet("background-color: #3498db; border-radius: 20px; font-size: 16px;")
        self.play_btn.clicked.connect(self.toggle_playback)
        
        self.video_slider = QSlider(Qt.Orientation.Horizontal)
        self.video_slider.setStyleSheet("QSlider::groove:horizontal { border: 1px solid #333; height: 8px; background: #2a2a2a; border-radius: 4px; } QSlider::handle:horizontal { background: #3498db; width: 14px; margin: -3px 0; border-radius: 7px; }")
        self.video_slider.sliderMoved.connect(self.set_video_position)
        
        self.time_label = QLabel("00:00 / 00:00")
        self.video_controls.addWidget(self.play_btn)
        self.video_controls.addWidget(self.video_slider)
        self.video_controls.addWidget(self.time_label)
        
        self.video_container = QWidget()
        self.video_container.setLayout(self.video_controls)
        self.video_container.hide() 
        main_layout.addWidget(self.video_container)

        self.bottom_bar = QHBoxLayout()
        self.palette_container = QHBoxLayout()
        
        tool_label = QLabel("Hotkeys: [V] Gray | [M] Mirror | [Scroll] Zoom | [Mid-Click] Pan | [Shift+Drag] Crop")
        tool_label.setStyleSheet("color: #7f8c8d; font-size: 14px;")
        
        self.pin_btn = QPushButton("📌 Pin to Moodboard")
        self.pin_btn.setStyleSheet("QPushButton { background-color: #9b59b6; color: white; border-radius: 4px; padding: 5px 15px; font-weight: bold; border: none; } QPushButton:hover { background-color: #8e44ad; }")
        self.pin_btn.clicked.connect(self.send_to_moodboard)
        
        self.bottom_bar.addWidget(tool_label)
        self.bottom_bar.addStretch()
        self.bottom_bar.addWidget(self.pin_btn)
        self.bottom_bar.addSpacing(15)
        self.bottom_bar.addLayout(self.palette_container)
        
        main_layout.addLayout(self.bottom_bar)
        
        self.media_player.positionChanged.connect(self.update_slider)
        self.media_player.durationChanged.connect(self.update_duration)

    def send_to_moodboard(self):
        if hasattr(self, 'main_window') and self.main_window and hasattr(self.main_window, 'moodboard'):
            self.main_window.moodboard.board.add_image(self.current_path)
            self.main_window.moodboard.show()
            self.pin_btn.setText("✅ Pinned!")
            self.pin_btn.setStyleSheet("QPushButton { background-color: #2ecc71; color: white; border-radius: 4px; padding: 5px 15px; font-weight: bold; border: none; }")
            QTimer.singleShot(1500, self.reset_pin_btn)

    def reset_pin_btn(self):
        self.pin_btn.setText("📌 Pin to Moodboard")
        self.pin_btn.setStyleSheet("QPushButton { background-color: #9b59b6; color: white; border-radius: 4px; padding: 5px 15px; font-weight: bold; border: none; } QPushButton:hover { background-color: #8e44ad; }")

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
            self.media_stack.setCurrentWidget(self.gif_label)
            self.video_container.hide()
            self.movie = QMovie(self.current_path)
            self.gif_label.setMovie(self.movie)
            self.movie.start()
            self.clear_palette()
        else:
            self.media_stack.setCurrentWidget(self.image_view)
            self.video_container.hide()
            # Loads the RAW high-resolution image, NO destructive downscaling
            self.original_qimage = QImage(self.current_path)
            self.apply_image_transformations()
            self.extract_and_display_palette()
            
        self.update_arrow_states()

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
            s, m = (ms // 1000) % 60, (ms // 60000) % 60
            return f"{m:02d}:{s:02d}"
        self.time_label.setText(f"{format_time(current)} / {format_time(total)}")

    def setup_hotkeys(self):
        QShortcut(QKeySequence("Left"), self).activated.connect(self.show_previous)
        QShortcut(QKeySequence("Right"), self).activated.connect(self.show_next)
        QShortcut(QKeySequence("V"), self).activated.connect(self.toggle_grayscale)
        QShortcut(QKeySequence("M"), self).activated.connect(self.toggle_mirror)
        QShortcut(QKeySequence("Space"), self).activated.connect(self.toggle_playback)
        QShortcut(QKeySequence("."), self).activated.connect(self.step_frame_forward)
        QShortcut(QKeySequence(","), self).activated.connect(self.step_frame_backward)

    def apply_image_transformations(self):
        if not self.original_qimage or self.media_stack.currentWidget() != self.image_view: return
        
        img = self.original_qimage.copy()
        if self.is_grayscale: img = img.convertToFormat(QImage.Format.Format_Grayscale8)
        if self.is_mirrored: img = img.mirrored(horizontal=True, vertical=False)
            
        pixmap = QPixmap.fromImage(img)
        self.image_view.update_image(pixmap)

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
        
    #HIGH-RES CROPPING LOGIC
    def start_crop(self, point):
        self.crop_origin = point
        self.rubber_band.setGeometry(QRect(self.crop_origin, QSize()))
        self.rubber_band.show()

    def update_crop(self, point):
        self.rubber_band.setGeometry(QRect(self.crop_origin, point).normalized())

    def finish_crop(self):
        if self.rubber_band.rect().width() > 20 and self.rubber_band.rect().height() > 20:
            #Map the visual rubberband box to the actual scene coordinates
            rect_in_view = self.rubber_band.geometry()
            rect_in_scene = self.image_view.mapToScene(rect_in_view).boundingRect()
            
            #Crop the raw high-res QImage data
            crop_rect = QRect(int(rect_in_scene.x()), int(rect_in_scene.y()), int(rect_in_scene.width()), int(rect_in_scene.height()))
            cropped_qimage = self.original_qimage.copy(crop_rect) # type: ignore
            
            #Fix black text on black bg
            dlg = QFileDialog(self, "Save Detail Crop", os.path.dirname(self.current_path), "Images (*.png *.jpg)")
            dlg.setStyleSheet("background-color: #2a2a2a; color: white;")
            dlg.setAcceptMode(QFileDialog.AcceptMode.AcceptSave)
            
            
            if dlg.exec() == QDialog.DialogCode.Accepted:
                save_path = dlg.selectedFiles()[0]
                cropped_qimage.save(save_path)
                print(f"Detail crop saved to {save_path}")    
        self.rubber_band.hide()