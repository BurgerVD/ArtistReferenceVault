import os
import random
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                             QPushButton, QWidget, QListWidget, QListWidgetItem, QComboBox,QTreeWidget, QTreeWidgetItem, QTreeWidgetItemIterator)
from PyQt6.QtCore import Qt, QTimer, QSize, QPoint
from PyQt6.QtGui import QPixmap, QImage, QKeySequence, QShortcut, QPainter, QColor

class GestureSession(QWidget):
    def __init__(self, image_paths, time_limit_sec,session_time_limit=None, parent=None):
        super().__init__(parent)
        self.image_paths = image_paths
        self.time_limit_sec = time_limit_sec
        self.session_time_limit = session_time_limit # Total session time
        
        self.current_index = 0
        self.time_remaining = time_limit_sec
        self.total_elapsed = 0 #Track total practice time
        self.is_paused = False
        
        self.is_grayscale = False
        self.is_mirrored = False
        self.original_qimage = None

        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.setStyleSheet("background-color: #0f0f12; color: white; border: 1px solid #333;")
        
        self.is_pinned_top = True
        self.MARGIN = 8 
        self._resize_edge = None
        self._drag_pos = None
        self.setMouseTracking(True)
        
        self.setup_ui()
        self.setup_hotkeys()
        
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.tick)
        
        self.resize(800, 800) 
        self.load_image()
        self.timer.start(1000)

    def setup_ui(self):
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(2, 2, 2, 2)
        self.main_layout.setSpacing(0)
        
        self.header = QWidget()
        self.header.setStyleSheet("background-color: #1a1a1a; border-bottom: 1px solid #333; border-top: none; border-left: none; border-right: none;")
        self.header.setFixedHeight(30)
        self.header.setMouseTracking(True)
        h_layout = QHBoxLayout(self.header)
        h_layout.setContentsMargins(10, 0, 10, 0)
        
        title_label = QLabel("⏱️ Gesture Practice")
        title_label.setStyleSheet("color: #aaaaaa; font-weight: bold; font-size: 12px; border: none;")
        h_layout.addWidget(title_label)
        h_layout.addStretch()
        
        self.pin_btn = QPushButton("📌 Pin Top")
        self.pin_btn.setFixedSize(60, 20)
        self.pin_btn.setStyleSheet("QPushButton { background-color: #3498db; color: white; border: none; font-weight: bold; border-radius: 4px; font-size: 10px; }")
        self.pin_btn.clicked.connect(self.toggle_pin_top)
        h_layout.addWidget(self.pin_btn)
        
        close_btn = QPushButton("✕")
        close_btn.setFixedSize(24, 24)
        close_btn.setStyleSheet("QPushButton { color: white; border: none; font-weight: bold; border-radius: 12px; } QPushButton:hover { background-color: #e74c3c; }")
        close_btn.clicked.connect(self.close)
        h_layout.addWidget(close_btn)
        
        self.main_layout.addWidget(self.header)

        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setStyleSheet("border: none;")
        self.main_layout.addWidget(self.image_label, stretch=1)
        
        self.overlay = QWidget(self)
        self.overlay.setStyleSheet("background-color: rgba(20, 20, 25, 0.95); border-radius: 10px; border: 1px solid #444;")
        overlay_layout = QHBoxLayout(self.overlay)
        overlay_layout.setContentsMargins(15, 10, 15, 10)
        
        # TRACKERS
        self.progress_label = QLabel()
        self.progress_label.setStyleSheet("font-size: 14px; font-weight: bold; color: #aaaaaa; border: none;")
        
        self.timer_label = QLabel(self.format_time(self.time_remaining))
        self.timer_label.setStyleSheet("font-size: 32px; font-weight: bold; color: #2ecc71; border: none;")
        
        self.total_time_label = QLabel()
        self.total_time_label.setStyleSheet("font-size: 14px; font-weight: bold; color: #f39c12; border: none;")
        
        # BUTTONS
        btn_style = "QPushButton { background-color: #34495e; color: white; border: none; padding: 6px 12px; border-radius: 6px; font-weight: bold; font-size: 12px;} QPushButton:hover { background-color: #3498db; }"
        
        self.play_btn = QPushButton("⏸ Pause")
        self.play_btn.setStyleSheet(btn_style)
        self.play_btn.clicked.connect(self.toggle_pause)
        
        prev_btn = QPushButton("◀")
        prev_btn.setStyleSheet(btn_style)
        prev_btn.clicked.connect(self.prev_image)
        
        next_btn = QPushButton("Skip ▶")
        next_btn.setStyleSheet(btn_style)
        next_btn.clicked.connect(self.next_image)
        
        # ASSEMBLE LAYOUT (Left to Right)
        overlay_layout.addWidget(self.progress_label)
        overlay_layout.addSpacing(15)
        overlay_layout.addWidget(self.timer_label)
        overlay_layout.addSpacing(15)
        overlay_layout.addWidget(self.total_time_label)
        
        overlay_layout.addStretch() # Pushes the buttons to the right side
        
        overlay_layout.addWidget(prev_btn)
        overlay_layout.addWidget(self.play_btn)
        overlay_layout.addWidget(next_btn)
        
        self.overlay.resize(650, 65)

    def toggle_pin_top(self):
        self.is_pinned_top = not self.is_pinned_top
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, self.is_pinned_top)
        self.pin_btn.setStyleSheet(f"QPushButton {{ background-color: {'#3498db' if self.is_pinned_top else '#555555'}; color: white; border: none; font-weight: bold; border-radius: 4px; font-size: 10px; }}")
        self.show()

    def resizeEvent(self, event): # type: ignore
        if event is None: return
        super().resizeEvent(event)
        x = (self.width() - self.overlay.width()) // 2
        y = self.height() - self.overlay.height() - 20
        self.overlay.move(x, y)
        if self.original_qimage: self.apply_image_transformations()

    def get_resize_edge(self, pos: QPoint):
        rect = self.rect()
        x, y, w, h = pos.x(), pos.y(), rect.width(), rect.height()
        edge = None
        if x < self.MARGIN: edge = Qt.Edge.LeftEdge
        if x > w - self.MARGIN: edge = (edge | Qt.Edge.RightEdge) if edge else Qt.Edge.RightEdge
        if y < self.MARGIN: edge = (edge | Qt.Edge.TopEdge) if edge else Qt.Edge.TopEdge
        if y > h - self.MARGIN: edge = (edge | Qt.Edge.BottomEdge) if edge else Qt.Edge.BottomEdge
        return edge

    def set_cursor_for_edge(self, edge):
        if edge == (Qt.Edge.TopEdge | Qt.Edge.LeftEdge) or edge == (Qt.Edge.BottomEdge | Qt.Edge.RightEdge): self.setCursor(Qt.CursorShape.SizeFDiagCursor)
        elif edge == (Qt.Edge.TopEdge | Qt.Edge.RightEdge) or edge == (Qt.Edge.BottomEdge | Qt.Edge.LeftEdge): self.setCursor(Qt.CursorShape.SizeBDiagCursor)
        elif edge and (edge & (Qt.Edge.LeftEdge | Qt.Edge.RightEdge)): self.setCursor(Qt.CursorShape.SizeHorCursor)
        elif edge and (edge & (Qt.Edge.TopEdge | Qt.Edge.BottomEdge)): self.setCursor(Qt.CursorShape.SizeVerCursor)
        else: self.setCursor(Qt.CursorShape.ArrowCursor)

    def mousePressEvent(self, event): # type: ignore
        if event is None: return
        if event.button() == Qt.MouseButton.LeftButton:
            edge = self.get_resize_edge(event.position().toPoint())
            if edge:
                self._resize_edge = edge
                self._drag_pos = event.globalPosition().toPoint()
                event.accept()
                return
            if self.header.underMouse():
                self._resize_edge = None
                self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
                event.accept()
                return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event): # type: ignore
        if event is None: return
        if event.buttons() == Qt.MouseButton.NoButton:
            edge = self.get_resize_edge(event.position().toPoint())
            self.set_cursor_for_edge(edge)
            super().mouseMoveEvent(event)
            return
        if event.buttons() == Qt.MouseButton.LeftButton and self._resize_edge:
            global_pos = event.globalPosition().toPoint()
            rect = self.geometry()
            if self._resize_edge & Qt.Edge.LeftEdge: rect.setLeft(global_pos.x())
            if self._resize_edge & Qt.Edge.RightEdge: rect.setRight(global_pos.x())
            if self._resize_edge & Qt.Edge.TopEdge: rect.setTop(global_pos.y())
            if self._resize_edge & Qt.Edge.BottomEdge: rect.setBottom(global_pos.y())
            self.setGeometry(rect)
            event.accept()
            return
        if event.buttons() == Qt.MouseButton.LeftButton and self._drag_pos and not self._resize_edge:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event): # type: ignore
        if event is None: return
        self._drag_pos = None
        self._resize_edge = None
        self.setCursor(Qt.CursorShape.ArrowCursor)
        super().mouseReleaseEvent(event)

    def format_time(self, seconds):
        m = seconds // 60
        s = seconds % 60
        return f"{m:02d}:{s:02d}"

    def tick(self):
        if self.is_paused: return
        
        
        if self.is_paused: return
        
        #Track Total Session Time
        self.total_elapsed += 1
        total_str = self.format_time(self.total_elapsed)
        if self.session_time_limit:
            total_limit_str = self.format_time(self.session_time_limit)
            self.total_time_label.setText(f"Total: {total_str} / {total_limit_str}")
            if self.total_elapsed >= self.session_time_limit:
                self.timer.stop()
                self.image_label.setText("⏱️ Session Time Reached! Great Job!")
                self.image_label.setStyleSheet("font-size: 32px; color: #f1c40f; font-weight: bold; border: none;")
                return
        else:
            self.total_time_label.setText(f"Total: {total_str}")
        
        #track image time
        self.time_remaining -= 1
        if self.time_remaining <= 5:
            self.timer_label.setStyleSheet("font-size: 28px; font-weight: bold; color: #e74c3c; border: none;") 
        else:
            self.timer_label.setStyleSheet("font-size: 28px; font-weight: bold; color: #2ecc71; border: none;")
        self.timer_label.setText(self.format_time(self.time_remaining))
        if self.time_remaining <= 0:
            self.next_image()

    def load_image(self):
        
        if not self.image_paths or self.current_index >= len(self.image_paths):
            self.timer.stop()
            self.timer_label.setText("Done!")
            self.image_label.setText("🎉 Session Complete!")
            self.image_label.setStyleSheet("font-size: 32px; color: #f1c40f; font-weight: bold; border: none;")
            return

        path = self.image_paths[self.current_index]
        self.original_qimage = QImage(path)
        self.is_grayscale = False
        self.is_mirrored = False
        self.apply_image_transformations()
        
        self.time_remaining = self.time_limit_sec
        self.timer_label.setText(self.format_time(self.time_remaining))
        self.timer_label.setStyleSheet("font-size: 28px; font-weight: bold; color: #2ecc71; border: none;")
        self.progress_label.setText(f"🖼️ {self.current_index + 1} / {len(self.image_paths)}")
        
    def apply_image_transformations(self):
        if not self.original_qimage or self.original_qimage.isNull(): return
        img = self.original_qimage.copy()
        if self.is_grayscale: img = img.convertToFormat(QImage.Format.Format_Grayscale8)
        if self.is_mirrored: img = img.mirrored(horizontal=True, vertical=False)
        pixmap = QPixmap.fromImage(img)
        scaled_pixmap = pixmap.scaled(self.width() - 10, self.height() - 100, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        self.image_label.setPixmap(scaled_pixmap)

    def next_image(self):
        if self.current_index < len(self.image_paths) - 1:
            self.current_index += 1
            self.load_image()
        else:
            # Reshuffle and loop seamlessly
            import random
            random.shuffle(self.image_paths)
            self.current_index = 0
            self.load_image() 

    def prev_image(self):
        if self.current_index > 0:
            self.current_index -= 1
            self.load_image()

    def toggle_pause(self):
        self.is_paused = not self.is_paused
        if self.is_paused:
            self.play_btn.setText("▶ Resume")
            self.play_btn.setStyleSheet("QPushButton { background-color: #2ecc71; color: white; border: none; padding: 6px 12px; border-radius: 6px; font-weight: bold; font-size: 12px;}")
        else:
            self.play_btn.setText("⏸ Pause")
            self.play_btn.setStyleSheet("QPushButton { background-color: #e67e22; color: white; border: none; padding: 6px 12px; border-radius: 6px; font-weight: bold; font-size: 12px;}")

    def toggle_grayscale(self):
        self.is_grayscale = not self.is_grayscale
        self.apply_image_transformations()

    def toggle_mirror(self):
        self.is_mirrored = not self.is_mirrored
        self.apply_image_transformations()

    def setup_hotkeys(self):
        QShortcut(QKeySequence("Space"), self).activated.connect(self.toggle_pause)
        QShortcut(QKeySequence("Right"), self).activated.connect(self.next_image)
        QShortcut(QKeySequence("Left"), self).activated.connect(self.prev_image)
        QShortcut(QKeySequence("V"), self).activated.connect(self.toggle_grayscale)
        QShortcut(QKeySequence("M"), self).activated.connect(self.toggle_mirror)


class GestureSetupDialog(QDialog):
    def __init__(self, db_manager, parent=None):
        super().__init__(parent)
        self.db = db_manager
        self.setWindowTitle("Gesture Practice Setup")
        self.setFixedSize(550, 600) # Made slightly taller to fit the tree comfortably
        self.setStyleSheet("background-color: #1e1e1e; color: white;")
        self.selected_images = []
        self.time_limit = 30
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("1. Select Folders to Practice From:"))
        
        # --- NEW: Select/Deselect All Buttons ---
        tree_controls = QHBoxLayout()
        self.select_all_btn = QPushButton("☑ Select All")
        self.select_all_btn.setStyleSheet("background-color: #34495e; color: white; border-radius: 4px; padding: 5px;")
        self.select_all_btn.clicked.connect(self.select_all)
        
        self.deselect_all_btn = QPushButton("☐ Deselect All")
        self.deselect_all_btn.setStyleSheet("background-color: #34495e; color: white; border-radius: 4px; padding: 5px;")
        self.deselect_all_btn.clicked.connect(self.deselect_all)
        
        tree_controls.addWidget(self.select_all_btn)
        tree_controls.addWidget(self.deselect_all_btn)
        layout.addLayout(tree_controls)

        # --- NEW: Hierarchical Tree View ---
        self.folder_tree = QTreeWidget()
        self.folder_tree.setHeaderHidden(True)
        self.folder_tree.setStyleSheet("""
            QTreeWidget { background-color: #2c3e50; border: 1px solid #34495e; border-radius: 4px; padding: 5px; }
            QTreeWidget::item { padding: 4px; }
        """)
        
        # Pull visual hierarchy from main window settings so it matches the sidebar
        custom_hierarchy = {}
        parent_widget = self.parent()
        if parent_widget and hasattr(parent_widget, 'settings'):
            #Use getattr to safely pull the dictionary
            app_settings = getattr(parent_widget, 'settings', {})
            custom_hierarchy = app_settings.get("custom_hierarchy", {})

        saved_folders = self.db.get_folders()
        item_map = {}
        top_level_items = []
        
        # Pass 1: Create all tree items
        for name, path in saved_folders:
            clean_path = os.path.normpath(path)
            item = QTreeWidgetItem([name])
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(0, Qt.CheckState.Unchecked)
            item.setData(0, Qt.ItemDataRole.UserRole, path)
            item_map[clean_path] = item
            
        # Pass 2: Link parents and children
        for name, path in saved_folders:
            clean_path = os.path.normpath(path)
            item = item_map[clean_path]
            
            # Check visual override, fallback to OS parent
            if path in custom_hierarchy:
                parent_key = custom_hierarchy[path]
            else:
                parent_key = os.path.dirname(clean_path)
                
            if parent_key == "root" or parent_key not in item_map:
                top_level_items.append(item)
            else:
                item_map[parent_key].addChild(item)
                
        self.folder_tree.addTopLevelItems(top_level_items)
        self.folder_tree.expandAll()
        
        # Connect the cascade logic AFTER building the tree
        self.folder_tree.itemChanged.connect(self.on_item_changed)
        
        layout.addWidget(self.folder_tree)
        
        # --- 2. Time Per Image ---
        layout.addWidget(QLabel("2. Time Per Image:"))
        self.time_combo = QComboBox()
        self.time_combo.setStyleSheet("background-color: #34495e; padding: 5px; border-radius: 4px;")
        self.time_combo.addItems(["30 Seconds", "45 Seconds", "1 Minute", "2 Minutes", "5 Minutes", "10 Minutes"])
        layout.addWidget(self.time_combo)
        
        # --- 3. Session Limit ---
        layout.addSpacing(10)
        layout.addWidget(QLabel("3. Session Limit:"))
        
        limit_layout = QHBoxLayout()
        self.limit_type = QComboBox()
        self.limit_type.addItems(["All Images", "Max Images", "Total Minutes"])
        self.limit_type.setStyleSheet("background-color: #34495e; padding: 5px; border-radius: 4px;")
        
        from PyQt6.QtWidgets import QSpinBox
        self.limit_value = QSpinBox()
        self.limit_value.setRange(1, 1000)
        self.limit_value.setValue(20)
        self.limit_value.setStyleSheet("background-color: #34495e; padding: 5px; border-radius: 4px;")
        self.limit_value.setEnabled(False) 
        
        self.limit_type.currentTextChanged.connect(lambda t: self.limit_value.setEnabled(t != "All Images"))
        
        limit_layout.addWidget(self.limit_type)
        limit_layout.addWidget(self.limit_value)
        layout.addLayout(limit_layout)
        
        layout.addSpacing(10)
        self.start_btn = QPushButton("🎨 Start Session")
        self.start_btn.setStyleSheet("QPushButton { background-color: #9b59b6; color: white; padding: 12px; font-size: 16px; font-weight: bold; border-radius: 6px; } QPushButton:hover { background-color: #8e44ad; }")
        self.start_btn.clicked.connect(self.start_session)
        layout.addWidget(self.start_btn)

    # --- Cascading Checkbox Logic ---
    def on_item_changed(self, item, column):
        # Block signals temporarily to prevent infinite recursion
        self.folder_tree.blockSignals(True)
        state = item.checkState(0)
        self.update_children_state(item, state)
        self.folder_tree.blockSignals(False)

    def update_children_state(self, item, state):
        for i in range(item.childCount()):
            child = item.child(i)
            child.setCheckState(0, state)
            self.update_children_state(child, state) # Recurse for nested folders

    def select_all(self):
        self.folder_tree.blockSignals(True)
        iterator = QTreeWidgetItemIterator(self.folder_tree)
        while iterator.value():
            item = iterator.value()
            if item: # Type Guard
                item.setCheckState(0, Qt.CheckState.Checked)
            iterator += 1
        self.folder_tree.blockSignals(False)
            
    def deselect_all(self):
        self.folder_tree.blockSignals(True)
        iterator = QTreeWidgetItemIterator(self.folder_tree)
        while iterator.value():
            item = iterator.value()
            if item: # Type Guard
                item.setCheckState(0, Qt.CheckState.Unchecked)
            iterator += 1
        self.folder_tree.blockSignals(False)

    def start_session(self):
        paths_to_scan = []
        
        iterator = QTreeWidgetItemIterator(self.folder_tree)
        while iterator.value():
            item = iterator.value()
            if item and item.checkState(0) == Qt.CheckState.Checked: # Type Guard
                paths_to_scan.append(item.data(0, Qt.ItemDataRole.UserRole))
            iterator += 1
                
        if not paths_to_scan: return 
            
        valid_exts = ['.jpg', '.jpeg', '.png', '.bmp', '.webp']
        for folder in paths_to_scan:
            if not os.path.exists(folder): continue
            for root, dirs, files in os.walk(folder):
                for f in files:
                    if os.path.splitext(f)[1].lower() in valid_exts:
                        self.selected_images.append(os.path.join(root, f))
                        
        if not self.selected_images: return
        
        # Remove duplicates in case parent and child were both checked
        self.selected_images = list(set(self.selected_images))
        import random
        random.shuffle(self.selected_images)
        
        limit_mode = self.limit_type.currentText()
        self.session_time_limit = None
        
        if limit_mode == "Max Images":
            self.selected_images = self.selected_images[:self.limit_value.value()]
        elif limit_mode == "Total Minutes":
            self.session_time_limit = self.limit_value.value() * 60
        
        time_str = self.time_combo.currentText()
        if "Seconds" in time_str: self.time_limit = int(time_str.split()[0])
        elif "Minute" in time_str: self.time_limit = int(time_str.split()[0]) * 60
        
        self.accept()