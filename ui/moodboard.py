import os
import json
from PyQt6.QtWidgets import (QGraphicsView, QGraphicsScene, QGraphicsPixmapItem, 
                             QWidget, QVBoxLayout, QPushButton, QHBoxLayout, QLabel, QMenu, QFileDialog)
from PyQt6.QtCore import Qt, QPoint, QRect
from PyQt6.QtGui import QPixmap, QPainter, QMouseEvent, QWheelEvent, QTransform

class MovableImage(QGraphicsPixmapItem):
    def __init__(self, image_path):
        super().__init__()
        self.image_path = image_path
        pixmap = QPixmap(image_path)
        
        if not pixmap.isNull():
            if pixmap.width() > 2000 or pixmap.height() > 2000:
                pixmap = pixmap.scaled(2000, 2000, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            self.setPixmap(pixmap)
        else:
            print(f"Warning: Could not render {image_path}")
        
        self.setFlag(QGraphicsPixmapItem.GraphicsItemFlag.ItemIsMovable)
        self.setFlag(QGraphicsPixmapItem.GraphicsItemFlag.ItemIsSelectable)
        self.setFlag(QGraphicsPixmapItem.GraphicsItemFlag.ItemSendsGeometryChanges)

class InfiniteBoard(QGraphicsView):
    def __init__(self,safe_parent=None):
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

    #Right Click Context Menu ---
    def contextMenuEvent(self, event): # type: ignore
        if event is None: return
        item = self.itemAt(event.pos())
        
        menu = QMenu(self)
        menu.setStyleSheet("background-color: #34495e; color: white; padding: 5px;")
        
        if item and isinstance(item, MovableImage):
            bring_front = menu.addAction("Bring to Front")
            send_back = menu.addAction("Send to Back")
            menu.addSeparator()
            remove_action = menu.addAction("Remove from Board")
            
            action = menu.exec(event.globalPos())
            if action == remove_action:
                self.board_scene.removeItem(item)
            elif action == bring_front:
                item.setZValue(item.zValue() + 1)
            elif action == send_back:
                item.setZValue(item.zValue() - 1)
                
        else:
            save_action = menu.addAction("💾 Save Moodboard")
            load_action = menu.addAction("📂 Load Moodboard")
            menu.addSeparator()
            clear_action = menu.addAction("🗑️ Clear Board")
            
            action = menu.exec(event.globalPos())
            if self.safe_parent: # Safely call functions using the reference
                if action == save_action:
                    self.safe_parent.save_board()
                elif action == load_action:
                    self.safe_parent.load_board()
            if action == clear_action:
                self.board_scene.clear()

    #Drag & Camera Controls ---
    def dragEnterEvent(self, event): # type: ignore
        if event is None: return
        mime_data = event.mimeData()
        if mime_data and mime_data.hasUrls():
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dragMoveEvent(self, event): # type: ignore
        if event is None: return
        mime_data = event.mimeData()
        if mime_data and mime_data.hasUrls():
            event.acceptProposedAction()
        else:
            super().dragMoveEvent(event)

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
        
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(4, 4, 4, 4) 
        self.main_layout.setSpacing(0)
        self.setStyleSheet("background-color: rgba(30, 30, 30, 0.98);")
        
        self.header = QWidget()
        self.header.setStyleSheet("background-color: rgba(20, 20, 20, 0.9); border-radius: 4px;")
        self.header.setFixedHeight(30)
        h_layout = QHBoxLayout(self.header)
        h_layout.setContentsMargins(10, 0, 10, 0)
        
        title = QLabel("Reference Vault - Moodboard")
        title.setStyleSheet("color: #aaaaaa; font-weight: bold; font-size: 12px;")
        h_layout.addWidget(title)
        h_layout.addStretch()
        
        # Minimize Button
        min_btn = QPushButton("—")
        min_btn.setFixedSize(24, 24)
        min_btn.setStyleSheet("QPushButton { color: white; border: none; font-weight: bold; border-radius: 12px; } QPushButton:hover { background-color: #f1c40f; }")
        min_btn.clicked.connect(self.showMinimized)
        h_layout.addWidget(min_btn)
        
        # Close Button
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

    # Save / Load Logic 
    def save_board(self):
        file_path, _ = QFileDialog.getSaveFileName(self, "Save Moodboard", "", "Vault Board (*.rvboard);;JSON (*.json)")
        if not file_path: return
        
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
        except Exception as e:
            print(f"Failed to save board: {e}")

    def load_board(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Load Moodboard", "", "Vault Board (*.rvboard);;JSON (*.json)")
        if not file_path: return
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
            self.board.board_scene.clear() # Wipe current board
            
            for obj in data:
                self.board.add_image(
                    image_path=obj.get("path"),
                    x=obj.get("x", 0.0),
                    y=obj.get("y", 0.0),
                    z=obj.get("z", 0.0),
                    scale=obj.get("scale", 1.0)
                )
        except Exception as e:
            print(f"Failed to load board: {e}")

    #Frameless Resizing
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