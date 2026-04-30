import os
import json
from PyQt6.QtWidgets import (QGraphicsView, QGraphicsScene, QGraphicsPixmapItem, 
                             QWidget, QVBoxLayout, QPushButton, QHBoxLayout, QLabel, QMenu, QFileDialog, QMessageBox, QSlider, QStyle)
from PyQt6.QtCore import Qt, QPoint, QRect, QRectF, QPointF
from PyQt6.QtGui import QPixmap, QPainter, QMouseEvent, QWheelEvent, QTransform, QPen, QColor, QBrush

class MovableImage(QGraphicsPixmapItem):
    def __init__(self, image_path):
        super().__init__()
        self.image_path = image_path
        pixmap = QPixmap(image_path)
        
        if not pixmap.isNull():
            if pixmap.width() > 2000 or pixmap.height() > 2000:
                pixmap = pixmap.scaled(2000, 2000, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            self.setPixmap(pixmap)
            
        self.setFlag(QGraphicsPixmapItem.GraphicsItemFlag.ItemIsMovable)
        self.setFlag(QGraphicsPixmapItem.GraphicsItemFlag.ItemIsSelectable)
        self.setFlag(QGraphicsPixmapItem.GraphicsItemFlag.ItemSendsGeometryChanges)
        self.setAcceptHoverEvents(True)
        
        self._resize_mode = None
        self._start_transform = QTransform()
        self._start_pos = QPointF()
        self._start_rect = self.boundingRect()

    def get_handles(self):
        rect = self.boundingRect()
        tx = self.transform()
        #increased base size for easier grabbing
        s = max(24.0, 32.0 / max(tx.m11(), tx.m22(), 0.01))
        half = s / 2.0
        
        #Centering the hitboxes perfectly over the edges/corners
        return {
            'tl': QRectF(rect.left() - half, rect.top() - half, s, s),
            't':  QRectF(rect.center().x() - half, rect.top() - half, s, s),
            'tr': QRectF(rect.right() - half, rect.top() - half, s, s),
            'r':  QRectF(rect.right() - half, rect.center().y() - half, s, s),
            'br': QRectF(rect.right() - half, rect.bottom() - half, s, s),
            'b':  QRectF(rect.center().x() - half, rect.bottom() - half, s, s),
            'bl': QRectF(rect.left() - half, rect.bottom() - half, s, s),
            'l':  QRectF(rect.left() - half, rect.center().y() - half, s, s),
        }

    def paint(self, painter, option, widget=None): # type: ignore
        if option is None or painter is None: 
            return
            
        option.state &= ~QStyle.StateFlag.State_Selected
        super().paint(painter, option, widget)
        
        if self.isSelected():
            tx = self.transform()
            s = max(1.0, 2.0 / max(tx.m11(), tx.m22(), 0.01))
            painter.setPen(QPen(QColor("#3498db"), s))
            painter.drawRect(self.boundingRect())
            
            painter.setBrush(QColor("#3498db"))
            for handle in self.get_handles().values():
                painter.drawRect(handle)

    def hoverMoveEvent(self, event): # type: ignore
        if event is None: return
        if self.isSelected():
            pos = event.pos()
            handles = self.get_handles()
            if handles['tl'].contains(pos) or handles['br'].contains(pos):
                self.setCursor(Qt.CursorShape.SizeFDiagCursor)
            elif handles['tr'].contains(pos) or handles['bl'].contains(pos):
                self.setCursor(Qt.CursorShape.SizeBDiagCursor)
            elif handles['t'].contains(pos) or handles['b'].contains(pos):
                self.setCursor(Qt.CursorShape.SizeVerCursor)
            elif handles['l'].contains(pos) or handles['r'].contains(pos):
                self.setCursor(Qt.CursorShape.SizeHorCursor)
            else:
                self.setCursor(Qt.CursorShape.ArrowCursor)
        else:
            self.setCursor(Qt.CursorShape.ArrowCursor)
        super().hoverMoveEvent(event)

    def mousePressEvent(self, event): # type: ignore
        if event is None: return
        if event.button() == Qt.MouseButton.LeftButton and self.isSelected():
            pos = event.pos()
            for mode, rect in self.get_handles().items():
                if rect.contains(pos):
                    self._resize_mode = mode
                    self._start_pos = event.scenePos()
                    self._start_transform = self.transform()
                    self._start_rect = self.boundingRect()
                    event.accept()
                    return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event): # type: ignore
        if event is None: return
        if self._resize_mode:
            delta = event.scenePos() - self._start_pos
            rect = self._start_rect
            
            sx = self._start_transform.m11()
            sy = self._start_transform.m22()
            
            dx = delta.x() / rect.width()
            dy = delta.y() / rect.height()

            # Proportional corners
            if self._resize_mode in ['tl', 'tr', 'bl', 'br']:
                scale_factor = max(dx, dy) if self._resize_mode == 'br' else min(dx, dy)
                sx = max(0.05, sx + dx)
                sy = max(0.05, sy + dy)
                # Force proportional
                avg_scale = (sx + sy) / 2
                sx, sy = avg_scale, avg_scale
            # Edge stretches (Non-uniform)
            elif self._resize_mode in ['l', 'r']:
                sx = max(0.05, sx + dx)
            elif self._resize_mode in ['t', 'b']:
                sy = max(0.05, sy + dy)

            self.setTransform(QTransform.fromScale(sx, sy))
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event): # type: ignore
        if event is None: return
        if self._resize_mode:
            self._resize_mode = None
            event.accept()
            self._mark_parent_dirty()
            return
        super().mouseReleaseEvent(event)

    def _mark_parent_dirty(self):
        scene = self.scene()
        if scene is None: return
        views = scene.views()
        if not views: return
        view = views[0]
        if hasattr(view, 'safe_parent') and getattr(view, 'safe_parent'): 
            getattr(view, 'safe_parent').mark_dirty()
            
class InfiniteBoard(QGraphicsView):
    def __init__(self, safe_parent=None):
        super().__init__()
        self.safe_parent = safe_parent
        self.board_scene = QGraphicsScene(self)
        self.setScene(self.board_scene)
        
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        self.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.FullViewportUpdate) 
        self.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
        
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setStyleSheet("background-color: #1e1e1e; border: none;")
        self.board_scene.setSceneRect(-50000, -50000, 100000, 100000) 
        
        self._is_panning = False
        self._pan_start_pos = QPoint()
        self.setAcceptDrops(True)

    def add_image(self, image_path, x: float = 0.0, y: float = 0.0, z: float = 0.0, scale: float = 1.0):
        if not os.path.exists(image_path): return
        item = MovableImage(image_path)
        item.setPos(x, y)
        item.setZValue(z)
        item.setScale(scale)
        self.board_scene.addItem(item)
        if self.safe_parent: self.safe_parent.mark_dirty()

    def auto_arrange_grid(self):
        items = self.board_scene.selectedItems()
        if not items: 
            items = self.board_scene.items()
            
        if not items: return
        
        # Simple grid packing math
        x_offset, y_offset, max_row_height = 0.0, 0.0, 0.0
        grid_width_limit = 2000.0 # Wrap images after this width
        
        for item in reversed(items): # Items usually return back-to-front
            if isinstance(item, MovableImage):
                item.setPos(x_offset, y_offset)
                bounds = item.sceneBoundingRect()
                
                x_offset += bounds.width() + 20.0
                max_row_height = max(max_row_height, bounds.height())
                
                if x_offset > grid_width_limit:
                    x_offset = 0.0
                    y_offset += max_row_height + 20.0
                    max_row_height = 0.0
                    
        if self.safe_parent: self.safe_parent.mark_dirty()

    def contextMenuEvent(self, event): # type: ignore
        if event is None: return
        item = self.itemAt(event.pos())
        
        menu = QMenu(self)
        menu.setStyleSheet("background-color: #34495e; color: white; padding: 5px;")
        
        if item and isinstance(item, MovableImage):
            bring_front = menu.addAction("Bring to Front")
            send_back = menu.addAction("Send to Back")
            menu.addSeparator()
            restore_action = menu.addAction("🔍 Restore 1:1 Original Size") 
            menu.addSeparator()
            remove_action = menu.addAction("Remove from Board")
            
            action = menu.exec(event.globalPos())
            if action == remove_action:
                self.board_scene.removeItem(item)
                if self.safe_parent: self.safe_parent.mark_dirty()
            elif action == bring_front:
                item.setZValue(item.zValue() + 1)
                if self.safe_parent: self.safe_parent.mark_dirty()
            elif action == send_back:
                item.setZValue(item.zValue() - 1)
                if self.safe_parent: self.safe_parent.mark_dirty()
            elif action == restore_action: 
                item.setTransform(QTransform()) #Resets scaling to 1.0
                if self.safe_parent: self.safe_parent.mark_dirty()
        else:
            arrange_action = menu.addAction("🗐 Auto-Arrange Images")
            menu.addSeparator()
            save_action = menu.addAction("💾 Save Moodboard")
            load_action = menu.addAction("📂 Load Moodboard")
            menu.addSeparator()
            clear_action = menu.addAction("🗑️ Clear Board")
            
            action = menu.exec(event.globalPos())
            
            if action == arrange_action:
                self.auto_arrange_grid()
            elif self.safe_parent:
                if action == save_action: self.safe_parent.save_board()
                elif action == load_action: self.safe_parent.load_board()
            if action == clear_action:
                self.board_scene.clear()
                if self.safe_parent: self.safe_parent.mark_dirty()

    def dragEnterEvent(self, event): # type: ignore
        if event is None: return
        mime_data = event.mimeData()
        if mime_data and mime_data.hasUrls(): event.acceptProposedAction()
        else: super().dragEnterEvent(event)

    def dragMoveEvent(self, event): # type: ignore
        if event is None: return
        mime_data = event.mimeData()
        if mime_data and mime_data.hasUrls(): event.acceptProposedAction()
        else: super().dragMoveEvent(event)

    def dropEvent(self, event): # type: ignore
        if event is None: return
        mime_data = event.mimeData()
        if mime_data and mime_data.hasUrls():
            scene_pos = self.mapToScene(event.position().toPoint())
            offset_x = 0.0
            urls = mime_data.urls()
            if urls:
                for url in urls:
                    if url.isLocalFile():
                        self.add_image(url.toLocalFile(), scene_pos.x() + offset_x, scene_pos.y())
                        offset_x += 200.0
            event.acceptProposedAction()
        else:
            super().dropEvent(event)

    def keyPressEvent(self, event): # type: ignore
        if event is None: return
        if event.key() == Qt.Key.Key_Delete or event.key() == Qt.Key.Key_Backspace:
            for item in self.board_scene.selectedItems():
                self.board_scene.removeItem(item)
            if self.safe_parent: self.safe_parent.mark_dirty()
        super().keyPressEvent(event)

    def wheelEvent(self, event): # type: ignore
        if event is None: return
        zoom_in_factor = 1.15
        zoom_out_factor = 1.0 / zoom_in_factor
        zoom_factor = zoom_in_factor if event.angleDelta().y() > 0 else zoom_out_factor
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.scale(zoom_factor, zoom_factor)

    def mousePressEvent(self, event): # type: ignore
        if event is None: return
        if event.button() == Qt.MouseButton.MiddleButton or (event.button() == Qt.MouseButton.LeftButton and event.modifiers() == Qt.KeyboardModifier.AltModifier):
            self._is_panning = True
            self._pan_start_pos = event.position().toPoint()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            self.setDragMode(QGraphicsView.DragMode.NoDrag) 
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event): # type: ignore
        if event is None: return
        if self._is_panning:
            delta = event.position().toPoint() - self._pan_start_pos
            h_bar = self.horizontalScrollBar()
            v_bar = self.verticalScrollBar()
            if h_bar and v_bar:
                h_bar.setValue(h_bar.value() - delta.x())
                v_bar.setValue(v_bar.value() - delta.y())
            self._pan_start_pos = event.position().toPoint()
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event): # type: ignore
        if event is None: return
        if self._is_panning:
            self._is_panning = False
            self.setCursor(Qt.CursorShape.ArrowCursor)
            self.setDragMode(QGraphicsView.DragMode.RubberBandDrag) 
            event.accept()
            return
        super().mouseReleaseEvent(event)

class PureRefOverlay(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        self.current_filepath = None
        self.is_dirty = False
        self.is_pinned_top = True
        self.is_locked = False #Window Locking
        
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(4, 4, 4, 4) 
        self.main_layout.setSpacing(0)
        self.setStyleSheet("background-color: rgba(30, 30, 30, 0.98);")
        
        self.header = QWidget()
        self.header.setStyleSheet("background-color: rgba(20, 20, 20, 0.9); border-radius: 4px;")
        self.header.setFixedHeight(30)
        h_layout = QHBoxLayout(self.header)
        h_layout.setContentsMargins(10, 0, 10, 0)
        
        self.title_label = QLabel()
        self.title_label.setStyleSheet("color: #aaaaaa; font-weight: bold; font-size: 12px;")
        self.update_title()
        h_layout.addWidget(self.title_label)
        h_layout.addStretch()
        
        #Window Opacity Slider
        opacity_label = QLabel("👁️")
        opacity_label.setStyleSheet("color: white; font-size: 14px;")
        h_layout.addWidget(opacity_label)
        
        self.opacity_slider = QSlider(Qt.Orientation.Horizontal)
        self.opacity_slider.setRange(10, 100)
        self.opacity_slider.setValue(100)
        self.opacity_slider.setFixedWidth(80)
        self.opacity_slider.setStyleSheet("QSlider::groove:horizontal { border: 1px solid #333; height: 4px; background: #2a2a2a; border-radius: 2px; } QSlider::handle:horizontal { background: #3498db; width: 10px; margin: -3px 0; border-radius: 5px; }")
        self.opacity_slider.valueChanged.connect(lambda v: self.setWindowOpacity(v / 100.0))
        h_layout.addWidget(self.opacity_slider)
        h_layout.addSpacing(10)
        
        #Lock Position Toggle
        self.lock_btn = QPushButton("🔓")
        self.lock_btn.setFixedSize(24, 24)
        self.lock_btn.setStyleSheet("QPushButton { color: white; border: none; font-size: 14px; } QPushButton:hover { background-color: #555; border-radius: 12px; }")
        self.lock_btn.clicked.connect(self.toggle_lock)
        h_layout.addWidget(self.lock_btn)

        #keep window above all others
        self.pin_btn = QPushButton("📌 Pin Top")
        self.pin_btn.setFixedSize(60, 20)
        self.pin_btn.setStyleSheet("QPushButton { background-color: #3498db; color: white; border: none; font-weight: bold; border-radius: 4px; font-size: 10px; }")
        self.pin_btn.clicked.connect(self.toggle_pin_top)
        h_layout.addWidget(self.pin_btn)
        
        #minimize
        min_btn = QPushButton("—")
        min_btn.setFixedSize(24, 24)
        min_btn.setStyleSheet("QPushButton { color: white; border: none; font-weight: bold; border-radius: 12px; } QPushButton:hover { background-color: #f1c40f; }")
        min_btn.clicked.connect(self.showMinimized)
        h_layout.addWidget(min_btn)
        
        #Maximize Button
        self.max_btn = QPushButton("☐")
        self.max_btn.setFixedSize(24, 24)
        self.max_btn.setStyleSheet("QPushButton { color: white; border: none; font-weight: bold; border-radius: 12px; } QPushButton:hover { background-color: #2ecc71; }")
        self.max_btn.clicked.connect(self.toggle_maximize)
        h_layout.addWidget(self.max_btn)
        
        
        #Close button
        close_btn = QPushButton("✕")
        close_btn.setFixedSize(24, 24)
        close_btn.setStyleSheet("QPushButton { color: white; border: none; font-weight: bold; border-radius: 12px; } QPushButton:hover { background-color: #e74c3c; }")
        close_btn.clicked.connect(self.close)
        h_layout.addWidget(close_btn)
        
        self.board = InfiniteBoard(safe_parent=self)
        self.main_layout.addWidget(self.header)
        self.main_layout.addWidget(self.board)
        self.resize(800, 600)
        
        self._drag_pos = None
        self._resize_edge = None
        self.MARGIN = 8 
        self.setMouseTracking(True)
        self.header.setMouseTracking(True)

        self.setMinimumSize(50, 50)
        self.header.hide()
        
    # --- Header Actions ---
    
    #Maximize window
    def toggle_maximize(self):
        if self.isMaximized():
            self.showNormal()
        else:
            self.showMaximized()
    
    
    
    def toggle_lock(self):
        self.is_locked = not self.is_locked
        self.lock_btn.setText("🔒" if self.is_locked else "🔓")
        # Visual feedback: Turn borders dark if locked
        if self.is_locked:
            self.setStyleSheet("background-color: rgba(15, 15, 15, 0.95); border: 2px solid #e74c3c;")
        else:
            self.setStyleSheet("background-color: rgba(30, 30, 30, 0.98); border: none;")

    def enterEvent(self, event): # type: ignore
        if event is None: return
        if not self.is_locked:
            self.header.show()
        super().enterEvent(event)

    def leaveEvent(self, event): # type: ignore
        if event is None: return
        self.header.hide()
        super().leaveEvent(event)
    
    def update_title(self):
        name = os.path.basename(self.current_filepath) if self.current_filepath else "Untitled"
        dirty_star = "*" if self.is_dirty else ""
        self.title_label.setText(f"Reference Vault - [{name}]{dirty_star}")

    def mark_dirty(self):
        if not self.is_dirty:
            self.is_dirty = True
            self.update_title()

    def toggle_pin_top(self):
        self.is_pinned_top = not self.is_pinned_top
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, self.is_pinned_top)
        self.pin_btn.setStyleSheet(f"QPushButton {{ background-color: {'#3498db' if self.is_pinned_top else '#555555'}; color: white; border: none; font-weight: bold; border-radius: 4px; font-size: 10px; }}")
        self.show()

    def save_board(self):
        from PyQt6.QtWidgets import QDialog # Ensure this is imported
        
        if self.current_filepath:
            file_path = self.current_filepath
        else:
            dlg = QFileDialog(self, "Save Moodboard", "", "Vault Board (*.rvboard);;JSON (*.json)")
            dlg.setStyleSheet("background-color: #2a2a2a; color: white;")
            dlg.setAcceptMode(QFileDialog.AcceptMode.AcceptSave)
            
            if dlg.exec() == QDialog.DialogCode.Accepted:
                file_path = dlg.selectedFiles()[0]
            else:
                return False
        
        data = []
        for item in self.board.board_scene.items():
            if isinstance(item, MovableImage):
                data.append({
                    "path": item.image_path,
                    "x": item.x(),
                    "y": item.y(),
                    "z": item.zValue(),
                    "scale": item.scale()
                })
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4)
            self.current_filepath = file_path
            self.is_dirty = False
            self.update_title()
            return True
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save board:\n{e}")
            return False

    def load_board(self):
        from PyQt6.QtWidgets import QDialog 
        
        if self.is_dirty:
            msg = QMessageBox(self)
            msg.setWindowTitle("Unsaved Changes")
            msg.setText("Save changes to your moodboard before loading a new one?")
            msg.setStyleSheet("background-color: #2a2a2a; color: white; QLabel { color: white; }")
            msg.setStandardButtons(QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel)
            
            reply = msg.exec()
            
            if reply == QMessageBox.StandardButton.Save:
                if not self.save_board():
                    return
            elif reply == QMessageBox.StandardButton.Cancel:
                return

        dlg = QFileDialog(self, "Load Moodboard", "", "Vault Board (*.rvboard);;JSON (*.json)")
        dlg.setStyleSheet("background-color: #2a2a2a; color: white;")
        dlg.setAcceptMode(QFileDialog.AcceptMode.AcceptOpen)
        
        if dlg.exec() == QDialog.DialogCode.Accepted:
            file_path = dlg.selectedFiles()[0]
        else:
            return
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
            self.board.board_scene.clear()
            for obj in data:
                self.board.add_image(
                    image_path=obj.get("path"),
                    x=obj.get("x", 0.0),
                    y=obj.get("y", 0.0),
                    z=obj.get("z", 0.0),
                    scale=obj.get("scale", 1.0)
                )
            self.current_filepath = file_path
            self.is_dirty = False
            self.update_title()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load board:\n{e}")

    def closeEvent(self, event): # type: ignore
        if event is None: return
        if self.is_dirty:
            msg = QMessageBox(self)
            msg.setWindowTitle("Unsaved Changes")
            msg.setText("Save changes to your moodboard before closing?")
            msg.setStyleSheet("background-color: #2a2a2a; color: white; QLabel { color: white; }")
            msg.setStandardButtons(QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel)
            
            reply = msg.exec()
            
            if reply == QMessageBox.StandardButton.Save:
                if not self.save_board():
                    event.ignore()
                    return
            elif reply == QMessageBox.StandardButton.Cancel:
                event.ignore()
                return
        event.accept()

    # --- Locked Frameless Resizing ---
    def get_resize_edge(self, pos: QPoint):
        rect = self.rect()
        x, y = pos.x(), pos.y()
        w, h = rect.width(), rect.height()
        edge = None
        if x < self.MARGIN: edge = Qt.Edge.LeftEdge
        if x > w - self.MARGIN: edge = (edge | Qt.Edge.RightEdge) if edge else Qt.Edge.RightEdge
        if y < self.MARGIN: edge = (edge | Qt.Edge.TopEdge) if edge else Qt.Edge.TopEdge
        if y > h - self.MARGIN: edge = (edge | Qt.Edge.BottomEdge) if edge else Qt.Edge.BottomEdge
        return edge

    def set_cursor_for_edge(self, edge):
        if edge == (Qt.Edge.TopEdge | Qt.Edge.LeftEdge) or edge == (Qt.Edge.BottomEdge | Qt.Edge.RightEdge):
            self.setCursor(Qt.CursorShape.SizeFDiagCursor)
        elif edge == (Qt.Edge.TopEdge | Qt.Edge.RightEdge) or edge == (Qt.Edge.BottomEdge | Qt.Edge.LeftEdge):
            self.setCursor(Qt.CursorShape.SizeBDiagCursor)
        elif edge and (edge & (Qt.Edge.LeftEdge | Qt.Edge.RightEdge)):
            self.setCursor(Qt.CursorShape.SizeHorCursor)
        elif edge and (edge & (Qt.Edge.TopEdge | Qt.Edge.BottomEdge)):
            self.setCursor(Qt.CursorShape.SizeVerCursor)
        else:
            self.setCursor(Qt.CursorShape.ArrowCursor)

    def mousePressEvent(self, event): # type: ignore
        if event is None: return
        # UX FIX: Prevent window moving/resizing if Padlock is locked
        if self.is_locked:
            super().mousePressEvent(event)
            return
            
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
        if self.is_locked:
            self.setCursor(Qt.CursorShape.ArrowCursor)
            super().mouseMoveEvent(event)
            return
            
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