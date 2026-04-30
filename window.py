
import os
import shutil
import json
import urllib.request
from pathlib import Path
from core.autotagger import AITaggerWorker
from core.cache import CacheManager
#controller for the main canvas area where images are displayed. It also handles drag and drop of folders to add them to the vault.
from PyQt6.QtWidgets import  QCheckBox,QStyle,QDialog,QMessageBox,QCompleter,QInputDialog,QSplitter,QFrame,QMenu,QLineEdit, QHBoxLayout, QListWidgetItem, QMainWindow,QVBoxLayout,QStackedWidget,QLabel,QListWidget, QWidget,QPushButton,QMessageBox,QListView,QTreeWidget,QTreeWidgetItem,QTreeWidgetItemIterator
from PyQt6.QtCore import Qt,QThread,pyqtSignal,QTimer,QStringListModel,QUrl
from ui.canvas import DropCanvas
from core.database import DatabaseManager
from PyQt6.QtGui import QContextMenuEvent, QMouseEvent,QPixmap,QIcon,QDesktopServices
from PIL import Image
from ui.moodboard import PureRefOverlay

#This class will work in the background and find untagged images when the app is opened
class BackgroundCrawlerThread(QThread):
    #emit the path of an image that needs to be tagged
    untagged_image_found = pyqtSignal(str)
    
    def __init__(self,folders_to_scan,db_manager):
        super().__init__()
        self.folders_to_scan = folders_to_scan
        self.db = db_manager
        # V2.2 FIX: Only scan extensions the AI can actually process!
        self.ai_compatible_extensions = ['.jpg', '.jpeg', '.png', '.bmp', '.webp']
    
    def run(self):
        print(f"Fast-Sync started scanning {len(self.folders_to_scan)} folder(s)...")
        
        #Get all known paths from the database IN ONE QUERY
        cursor = self.db.conn.cursor()
        cursor.execute("SELECT image_path FROM tags")
        db_known_files = set(row[0] for row in cursor.fetchall())
        
        #Gather all current files from the OS
        os_current_files = set()
        for folder_path in self.folders_to_scan:
            if not os.path.exists(folder_path): continue # Safety check
            for root, dirs, files in os.walk(folder_path):
                for file in files:
                    if self.isInterruptionRequested(): return
                    
                    ext = os.path.splitext(file)[1].lower()
                    # Only add AI-compatible formats to the tagging queue
                    if ext in self.ai_compatible_extensions:
                        full_path = os.path.join(root, file)
                        os_current_files.add(full_path)
                        
        
        # Finds items in the OS that do not exist in the DB
        new_files = os_current_files - db_known_files
        
        print(f"Fast-Sync complete. Found {len(new_files)} new images.")
        
        for file_path in new_files:
            if self.isInterruptionRequested(): return
            
            # Simple corruption check
            if os.path.getsize(file_path) > 0:
                self.untagged_image_found.emit(file_path)


#This class is the lightbox when a image is double clicked it will show the full res image
class LightBox(QDialog):
    def __init__(self,image_path,parent=None):
        super().__init__(parent)
        #borderless 
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint| Qt.WindowType.Dialog)
        self.setModal(True) #Dim the app 
        self.setStyleSheet("background-color:rgba(0,0,0,0.95);")
        
        layout=QVBoxLayout(self)
        layout.setContentsMargins(0,0,0,0)
        
        self.image_label =QLabel()
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.image_label)
        
        #load original file
        pixmap= QPixmap(image_path)
        
        #get users screen size so imag is not bigger than monitor res
        
        screen=self.screen().availableGeometry() # type: ignore
        scaled_pixmap=pixmap.scaled(
            screen.width()-100,
            screen.height()-100,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )
        self.image_label.setPixmap(scaled_pixmap)

    #If user clicks anywhere on the image, it will be closed
    def mousePressEvent(self,event): #type:ignore
        self.accept()
#---------------
#UPdate checker
class UpdateCheckerThread(QThread):
    # Emits the new version string and the download URL if an update is found
    update_available = pyqtSignal(str, str) 

    def __init__(self, current_version):
        super().__init__()
        self.current_version = current_version
       
        self.api_url = "https://api.github.com/repos/ShaheerVD/ArtistReferenceVault/releases/latest"

    def run(self):
        try:
         
            req = urllib.request.Request(self.api_url, headers={'User-Agent': 'ReferenceVault-App'})
            with urllib.request.urlopen(req, timeout=5) as response:
                data = json.loads(response.read().decode())
                
                latest_version = data.get('tag_name', '')
                release_url = data.get('html_url', '')

                #If GitHub's version doesn't match the app's version, trigger the popup
                if latest_version and latest_version != self.current_version:
                    self.update_available.emit(latest_version, release_url)
                    
        except Exception as e:
            #If user have no internet  fail silently so the app still works normally
            print(f"Update check skipped/failed: {e}")

#Pop up window
class SettingsDialog(QDialog):
    
    def __init__(self, main_window):
        super().__init__(main_window)
        self.main_window = main_window
        self.setWindowTitle("Preferences")
        self.setStyleSheet("background-color: #2a2a2a; color: white; font-size: 14px;")
        self.setFixedSize(350, 220)
        
        
        layout = QVBoxLayout(self)
        
        self.auto_tag_cb = QCheckBox("Auto-Tag Images on Import")
        self.auto_tag_cb.setChecked(self.main_window.settings.get("auto_tag_import", True))
        self.auto_tag_cb.toggled.connect(self.save_settings)
        layout.addWidget(self.auto_tag_cb)

        self.cache_all_btn = QPushButton("⚡ Cache All Vault Images")
        self.cache_all_btn.setStyleSheet("background-color: #8e44ad; padding: 8px; border-radius: 4px; font-weight: bold;")
        self.cache_all_btn.clicked.connect(self.main_window.action_cache_all)
        layout.addWidget(self.cache_all_btn)
        
        
        self.load_ai_cb = QCheckBox("Load AI Tagger on Startup")
        #Load the current saved setting
        self.load_ai_cb.setChecked(self.main_window.settings.get("load_ai_on_startup", True))
        
        #Instantly save the setting whenever the user ticks/unticks the box
        self.load_ai_cb.toggled.connect(self.save_settings)
        layout.addWidget(self.load_ai_cb)
        
        self.clear_cache_btn = QPushButton("🗑️ Clear Thumbnail Cache")
        self.clear_cache_btn.setStyleSheet("background-color: #e67e22; padding: 8px; border-radius: 4px; font-weight: bold;")
        self.clear_cache_btn.clicked.connect(self.main_window.action_clear_cache)
        layout.addWidget(self.clear_cache_btn)
        
        save_btn = QPushButton("Save & Close")
        save_btn.setStyleSheet("background-color: #3498db; padding: 8px; border-radius: 4px; font-weight: bold;")
        save_btn.clicked.connect(self.accept)
        layout.addWidget(save_btn)

    def save_settings(self):
        #Save the new preference to the main app's memory and JSON file instantly
        self.main_window.settings["load_ai_on_startup"] = self.load_ai_cb.isChecked()
        self.main_window.settings["auto_tag_import"] = self.auto_tag_cb.isChecked()
        try:
            with open(self.main_window.settings_path, "w") as f:
                json.dump(self.main_window.settings, f, indent=4)
        except Exception as e:
            print(f"Failed to save settings: {e}")

    def closeEvent(self, event): #type:ignore
        #Ensure it saves even if the user just clicks the 'X' in the corner of the window
        self.save_settings()
        super().closeEvent(event)
        
    def accept(self):
        self.save_settings()
        super().accept()


class VaultTreeWidget(QTreeWidget):
    folder_moved = pyqtSignal(object, object)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
    def dropEvent(self, event): # type: ignore
        if event is None: return
        dragged_items = self.selectedItems()
        target_item = self.itemAt(event.position().toPoint())
        
        if dragged_items and target_item:
            self.folder_moved.emit(dragged_items[0], target_item)
            
       
        event.ignore()



#----------------------------------------------------#
#this class is the main window of the application. It contains the sidebar and the canvas. It listens for signals from the canvas when a folder is dropped and adds it to the sidebar. It also handles clicks on the sidebar to load the corresponding images in the canvas.
class ReferenceVault(QMainWindow):
    def __init__(self):
        super().__init__()
              
        self.setWindowTitle("Reference Vault")
        self.resize(1000,750)
        
        #Global tooltip styling
        self.setStyleSheet("""
            QToolTip {
                color: #ffffff;
                background-color: #2a2a2a;
                border: 1px solid #7f8c8d;
                font-size: 13px;
                padding: 4px;
            }
        """
            
        )
        
        icon_path=os.path.join(os.getcwd(),"app_icon.ico")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        
        
        #initialize Core 
        self.master_vault_path = self.setup_master_vault()
        
        self.db = DatabaseManager() 
        self.cache_manager = CacheManager()
        #Settings manager
        self.settings_path = os.path.join(self.master_vault_path, "vault_settings.json")
        self.settings = {"load_ai_on_startup": True, "expanded_folders": [], "auto_tag_import": True}
        if os.path.exists(self.settings_path):
            with open(self.settings_path, "r") as f:
                self.settings.update(json.load(f))
        
        
        #update checker
        self.CURRENT_VERSION = "v2.0.1" 
        
        self.update_checker = UpdateCheckerThread(self.CURRENT_VERSION)
        self.update_checker.update_available.connect(self.show_update_dialog)
        self.update_checker.start()
        
        
        #Load the Ai model 
        self.ai_engine = AITaggerWorker()
        
        #fix ui freezing
        self.tag_buffer = []
        self.db_commit_timer = QTimer()
        self.db_commit_timer.timeout.connect(self.process_tag_buffer)
        self.db_commit_timer.start(2000) # Tick every 2 seconds
        
        self.ai_engine.engine_loaded.connect(self.on_ai_loaded)
        self.ai_engine.engine_unloaded.connect(self.on_ai_unloaded)
        self.ai_engine.tags_generated.connect(self.save_generated_tags)
       
        self.ai_engine.engine_ready.connect(self.on_ai_ready)
        
        
        self.current_folder_path = None #track the currently loaded folder path to avoid reloading if the same folder is clicked again
        #main window
        self.ai_engine.queue_updated.connect(self.update_ai_status)
        #Base Layout
        #central contaainer and horizontal layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        
        #remove margins and spacing
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        #QSplitter allow user to resize sidebar
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        main_layout.addWidget(self.splitter)
        #sidebar for folders and tags
        self.sidebar=QFrame()
        self.sidebar.setFixedWidth(250)
        self.sidebar.setStyleSheet("background-color: #2c3e50;color: white;")
        sidebar_layout = QVBoxLayout(self.sidebar)
        # AI buttons
        self.toggle_ai_btn = QPushButton("🛑 Unload Tagger")
        self.toggle_ai_btn.setStyleSheet("background-color: #c0392b; color: white; border-radius: 4px; padding: 8px;")
        self.toggle_ai_btn.clicked.connect(self.toggle_ai_engine)
        self.ai_controls_layout = QHBoxLayout()
        #START IN "RESUME" STATE (Green) because the engine starts paused
        self.pause_ai_btn = QPushButton("▶ Resume Queue")
        self.pause_ai_btn.setStyleSheet("""
            QPushButton { background-color: #2ecc71; color: white; border-radius: 4px; padding: 5px; }
            QPushButton:disabled { background-color: #555555; color: #888888; }
        """)
        self.pause_ai_btn.clicked.connect(self.toggle_ai_pause)
        self.pause_ai_btn.setEnabled(False) # Start disabled
        
        
        
        self.stop_ai_btn = QPushButton("⏹ Clear Queue")
        self.stop_ai_btn.setStyleSheet("""
            QPushButton { background-color: #e74c3c; color: white; border-radius: 4px; padding: 5px; }
            QPushButton:disabled { background-color: #555555; color: #888888; }
        """)
        self.stop_ai_btn.clicked.connect(self.ai_engine.clear_queue)
        self.stop_ai_btn.setEnabled(False) # Start disabled
        
        self.ai_controls_layout.addWidget(self.pause_ai_btn)
        self.ai_controls_layout.addWidget(self.stop_ai_btn)
        sidebar_layout.addLayout(self.ai_controls_layout)
        
        
        
        # Settings Button 
        self.settings_btn = QPushButton("⚙️ Settings")
        self.settings_btn.setStyleSheet("background-color: #2c3e50; color: white; border-radius: 4px; padding: 8px; font-weight: bold;")
        self.settings_btn.clicked.connect(self.open_settings)
        
        
        
        
        #collapsible Tree Sidebar
       # self.folder_list = QTreeWidget()
        self.folder_list = VaultTreeWidget()
        self.folder_list.setHeaderHidden(True)
        self.folder_list.setDragEnabled(True)
        self.folder_list.setAcceptDrops(True)
        self.folder_list.setDropIndicatorShown(True)
        self.folder_list.setDragDropMode(QTreeWidget.DragDropMode.InternalMove)
        self.folder_list.folder_moved.connect(self.handle_folder_move)
        
        self.folder_list.setStyleSheet("""
            QTreeWidget {
                border: none;
                font-size: 14px;
                background-color: #2c3e50;
                color: white;
            }
            QTreeWidget::item {
                padding: 5px;
            }
            QTreeWidget::item:selected {
                background-color: #34495e;
            }
        """)
        #connect folder click to load images in canvas
        self.folder_list.itemClicked.connect(self.on_sidebar_folder_clicked)
        sidebar_layout.addWidget(self.folder_list)
        
        self.folder_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.folder_list.customContextMenuRequested.connect(self.on_folder_context_menu)
        
        
        
        #Show ai status on UI
        self.ai_status_label = QLabel("🤖 Auto Tagger: Sleeping")
        self.ai_status_label.setStyleSheet("color: #2ecc71; padding: 10px; font-weight: bold; background-color: #273746; border-radius: 5px;")
        self.ai_status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sidebar_layout.addWidget(self.ai_status_label)
        
        
        
        #add drop canvas for image grid
        self.canvas = DropCanvas(self.db)
        self.canvas.folder_dropped.connect(self.add_folder_to_sidebar)
        
        #When Canvas announces a new Image, put it into the Ai's queue
        self.canvas.image_added.connect(self.handle_new_image)
        
        #catch distress signal and trigger a popup
        self.canvas.needs_new_folder.connect(self.create_custom_folder)
        
        #connect double click to lightbox
        self.canvas.grid.itemDoubleClicked.connect(self.open_lightbox)
        
        self.canvas.grid.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.canvas.grid.customContextMenuRequested.connect(self.on_image_context_menu)
        
        #load folders from database and add to sidebar on startup
        self.refresh_sidebar()

       #Search bar
        self.search_bar = QLineEdit()
        self.search_bar.setText("Loading autotagger..please wait")
        self.search_bar.setEnabled(False)
        self.search_bar.setStyleSheet("""
           QLineEdit{
               background-color:#2a2a2a;
               color:white;
               border:1px solid #3d3d3d;
               border-radius:4px;
               padding:8px;
               font-size:14px;
           }                     
           QLineEdit:focus{
               border:1px solid #3498db;
           }      
        """)
        
        #autoComplete for search
        self.completer = QCompleter([])
        self.completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        
        drop_down_menu = QListView()
        drop_down_menu.setStyleSheet("""
            QListView {
                background-color: #2a2a2a; 
                color: white; 
                border: 1px solid #3d3d3d;
            }
            QListView::item:selected {
                background-color: #3498db;
            }
        """)
        self.completer.setPopup(drop_down_menu)
        
        
        self.search_bar.setCompleter(self.completer)
        self.search_bar.textChanged.connect(self.perform_search)

        #hELP BUTTON
        self.help_btn = QPushButton("?")
        self.help_btn.setFixedSize(38, 38)
        self.help_btn.setStyleSheet("""
            QPushButton {
                background-color: #2a2a2a; color: #888888;
                border: 1px solid #3d3d3d; border-radius: 4px;
                font-size: 18px; font-weight: bold;
            }
            QPushButton:hover { background-color: #3d3d3d; color: white; }
        """)
        self.help_btn.clicked.connect(self.show_help)

        #TOP BAR LAYOUT
        self.top_bar = QFrame()
        self.top_bar.setStyleSheet("background-color: #1e1e1e; border-bottom: 1px solid #3d3d3d;")
        top_bar_layout = QHBoxLayout(self.top_bar)
        top_bar_layout.setContentsMargins(10, 10, 10, 10)

        #Gesture mode button
        self.gesture_btn = QPushButton("⏱️ Gesture Practice")
        self.gesture_btn.setStyleSheet("background-color: #e67e22; color: white; border-radius: 4px; padding: 8px; font-weight: bold;")
        self.gesture_btn.clicked.connect(self.start_gesture_mode)
        top_bar_layout.addWidget(self.gesture_btn)
        
        
        #Moodboard Button
        self.moodboard = PureRefOverlay(self)
        self.moodboard.hide()
        self.board_btn = QPushButton("🎨 Moodboard")
        self.board_btn.setStyleSheet("background-color: #9b59b6; color: white; border-radius: 4px; padding: 8px; font-weight: bold;")
        self.board_btn.clicked.connect(self.toggle_moodboard)

        #AI Toggle Button
        self.toggle_ai_btn = QPushButton("🛑 Unload Tagger")
        self.toggle_ai_btn.setStyleSheet("background-color: #c0392b; color: white; border-radius: 4px; padding: 8px; font-weight: bold;")
        self.toggle_ai_btn.clicked.connect(self.toggle_ai_engine)

        #Settings Button
        self.settings_btn = QPushButton("⚙️ Settings")
        self.settings_btn.setStyleSheet("background-color: #2c3e50; color: white; border-radius: 4px; padding: 8px; font-weight: bold;")
        self.settings_btn.clicked.connect(self.open_settings)

        #Assemble the Top Bar (Left to Right)
        top_bar_layout.addWidget(self.board_btn)
        top_bar_layout.addWidget(self.search_bar)
        top_bar_layout.addWidget(self.toggle_ai_btn)
        top_bar_layout.addWidget(self.settings_btn)
        top_bar_layout.addWidget(self.help_btn)

        #BUILD RIGHT SIDE PANEL
        right_side_widget = QWidget()
        right_side_widget.setStyleSheet("background-color: #1e1e1e;") 
        right_side_layout = QVBoxLayout(right_side_widget)
        right_side_layout.setContentsMargins(0, 0, 0, 0)
        right_side_layout.setSpacing(0)
        
        right_side_layout.addWidget(self.top_bar)
        right_side_layout.addWidget(self.canvas)
        
        # ASSEMBLE MAIN SPLITTER
        self.splitter.addWidget(self.sidebar)
        self.splitter.addWidget(right_side_widget)
        self.splitter.setSizes([250, 750])

        #STARTUP LOGIC
        # 1. Start AI Engine after 2 seconds (Let the UI render first)
        if self.settings["load_ai_on_startup"]:
            QTimer.singleShot(2000, lambda: self.ai_engine.start(QThread.Priority.NormalPriority))
        else:
            self.ai_status_label.setText("🤖 Tagger Disabled on Startup") 
            self.toggle_ai_btn.setText("▶️ Load Tagger")
            self.toggle_ai_btn.setStyleSheet("background-color: #2ecc71; color: white; border-radius: 4px; padding: 8px; font-weight: bold;")
            self.search_bar.setEnabled(True)
            self.search_bar.clear()
            self.search_bar.setPlaceholderText("Search for images here (e.g. 'girl','sword')...")
            self.update_search_autocomplete()
            
        # 2. Trigger background crawler after 4 seconds (Prevent HDD thrashing on boot)
        saved_folders = self.db.get_folders()
        folder_paths = [path for name, path in saved_folders] 
        if folder_paths:
            QTimer.singleShot(4000, lambda: self.start_crawler(folder_paths))

        # 3. Restore Last opened Folder (Instant)
        last_folder = self.settings.get("last_folder")
        if last_folder and os.path.exists(last_folder):
            iterator = QTreeWidgetItemIterator(self.folder_list)
            while iterator.value():
                tree_item = iterator.value()
                data = tree_item.data(0, Qt.ItemDataRole.UserRole) #type:ignore
                if isinstance(data, dict) and data.get("type") == "physical" and data.get("path") == last_folder:
                    self.folder_list.setCurrentItem(tree_item)
                    self.on_sidebar_folder_clicked(tree_item)
                    break
                iterator += 1
            
    def toggle_moodboard(self):
        if self.moodboard.isVisible():
            self.moodboard.hide()
        else:
            self.moodboard.show()
            
                   
    
    
    def toggle_ai_engine(self):
        #Smart toggle that flips between Loading and Unloading the VRAM
        if self.ai_engine.session is not None:
            # It's currently loaded -> Unload it
            self.ai_engine.unload_engine()
            self.toggle_ai_btn.setText("▶️ Load Tagger")
            self.toggle_ai_btn.setStyleSheet("background-color: #2ecc71; color: white; border-radius: 4px; padding: 8px; font-weight: bold;")
        
        
        else:
            # It's currently unloaded -> Load it
            #If the thread was never started (disabled on startup), start it.
            # The run() function will naturally find the model path and call load_engine()
            if not self.ai_engine.isRunning():
                self.ai_engine.start()
            else:
                self.ai_engine.load_engine()
            self.toggle_ai_btn.setText("🛑 Unload Tagger")
            self.toggle_ai_btn.setStyleSheet("background-color: #c0392b; color: white; border-radius: 4px; padding: 8px; font-weight: bold;")
            self.on_ai_loaded()

    def open_settings(self):
        #Spawns the  Preferences window
        dialog = SettingsDialog(self)
        dialog.exec()
    
    #UI FUNCTIONS----------------------------------------------------------------
    #create master reference library folder in documents
    def setup_master_vault(self):
        home_dir = str(Path.home())
        vault_path = os.path.join(home_dir,"Documents","ReferenceVault_Library")
        os.makedirs(vault_path,exist_ok=True)
        return vault_path
    
    #create folder
    def create_custom_folder(self,parent_path=None):
        # If user didn't right-click a specific folder, default to the master vault root
        if parent_path is None:
            parent_path = self.master_vault_path
        
        folder_name, ok= QInputDialog.getText(self,"New Vault Folder","Enter folder name:")
        
        if ok and folder_name.strip():
            folder_name= folder_name.strip()
            #build path inside the selected parent folder
            new_path = os.path.join(parent_path, folder_name)
            os.makedirs(new_path, exist_ok=True)
            #add to db and sidebar visually
            self.add_folder_to_sidebar(folder_name,new_path)
            print(f"Created custom vault folder: {new_path}")
        
            #Make ui select the new folder
            #loop through sidebar to find new item just created
            iterator = QTreeWidgetItemIterator(self.folder_list)
            while iterator.value():
                item = iterator.value()
                if item.data(0, Qt.ItemDataRole.UserRole) == new_path: #type:ignore
                    self.folder_list.setCurrentItem(item)
                    self.current_folder_path = new_path
                    self.canvas.load_images_from_path(new_path)
                    break
                iterator += 1
     
    def on_folder_context_menu(self, pos):
        item = self.folder_list.itemAt(pos)
        menu = QMenu(self)
        menu.setStyleSheet("background-color: #34495e;color:white;padding:5px;")
        
        add_action = menu.addAction("+ New Folder") 
        globalretag_action = menu.addAction("Retag All")
        menu.addSeparator() 
        
        rename_action = None
        retag_action = None
        remove_ref_action = None
        delete_perm_action = None
        delete_smart_action = None
        
        if item is not None:
            self.folder_list.setCurrentItem(item)
            data = item.data(0, Qt.ItemDataRole.UserRole)
            
            is_physical = isinstance(data, dict) and data.get("type") == "physical"
            is_smart = isinstance(data, dict) and data.get("type") == "smart"
            
            if is_physical:
                rename_action = menu.addAction("Rename Folder")
                retag_action = menu.addAction("Re-Tag Images")
                menu.addSeparator()
                remove_ref_action = menu.addAction("Remove Folder from Vault (Keep Files)")
                delete_perm_action = menu.addAction("Delete Folder Permanently from PC")
            elif is_smart:
                delete_smart_action = menu.addAction("Delete Smart Collection")
            
        action = menu.exec(self.folder_list.viewport().mapToGlobal(pos)) #type:ignore
        if action is None: return
        
        if action == globalretag_action:
            self.global_retag_vault()   
        elif action == add_action:
            if item is not None and isinstance(item.data(0, Qt.ItemDataRole.UserRole), dict):
                path = item.data(0, Qt.ItemDataRole.UserRole).get("path")
                self.create_custom_folder(parent_path=path)
            else:
                self.create_custom_folder()
         #Rename       
        elif item is not None: 
            data = item.data(0, Qt.ItemDataRole.UserRole)
            if rename_action and action == rename_action:  
                old_path = data.get("path")
                old_name = item.text(0)
                new_name, ok = QInputDialog.getText(self, "Rename Folder", "Enter new folder name:", text=old_name)
                if ok and new_name.strip() and new_name != old_name:
                    new_name = new_name.strip()
                    parent_dir = os.path.dirname(old_path)
                    new_path = os.path.join(parent_dir, new_name)
                    try:
                        # 1. Rename on OS FIRST
                        os.rename(old_path, new_path)
                        
                        # 2. Rename in DB (Will raise Exception if it fails now)
                        self.db.rename_folder(old_path, new_path, new_name)
                        
                        # 3. Safely update the visual hierarchy JSON so it doesn't break
                        if "custom_hierarchy" in self.settings:
                            import json
                            hierarchy = self.settings["custom_hierarchy"]
                            new_hierarchy = {}
                            
                            old_base = os.path.normpath(old_path)
                            new_base = os.path.normpath(new_path)
                            
                            for k, v in hierarchy.items():
                                if k == old_base or k.startswith(old_base + os.sep):
                                    new_k = new_base + k[len(old_base):]
                                else:
                                    new_k = k
                                    
                                if v == old_base or v.startswith(old_base + os.sep):
                                    new_v = new_base + v[len(old_base):]
                                else:
                                    new_v = v
                                    
                                new_hierarchy[new_k] = new_v
                                
                            self.settings["custom_hierarchy"] = new_hierarchy
                            with open(self.settings_path, "w") as f:
                                json.dump(self.settings, f)
                        
                        self.current_folder_path = new_path
                        self.refresh_sidebar()
                        self.canvas.load_images_from_path(new_path)
                    except Exception as e:
                        # CRITICAL: If DB or JSON fails, revert the OS rename!
                        if os.path.exists(new_path) and not os.path.exists(old_path):
                            try:
                                os.rename(new_path, old_path)
                            except:
                                pass
                        QMessageBox.critical(self, "Error", f"Failed to rename folder.\n\n{e}")
                        self.refresh_sidebar()
             
            elif retag_action and action == retag_action:
                self.retag_folder(data.get("path"))           
            elif remove_ref_action and action == remove_ref_action:
                self.remove_folder(item, permanent=False)    
            elif delete_perm_action and action == delete_perm_action:
                self.remove_folder(item, permanent=True)
            elif delete_smart_action and action == delete_smart_action:
                self.db.delete_smart_folder(item.text(0))
                self.refresh_sidebar()
        
    
    
    
    def global_retag_vault(self):
        reply = QMessageBox.warning(
            self,
            "Global Re-Tag",
            "Are you sure you want to completely wipe and re-tag EVERY image in your vault?\nThis may take a long time.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            #Wake up AI if disabled
            if not self.ai_engine.isRunning():
                self.ai_engine.start()
                
            cursor = self.db.conn.cursor()
            cursor.execute("SELECT image_path FROM tags")
            all_images = list(set([row[0] for row in cursor.fetchall()]))
            
            for path in all_images:
                if os.path.exists(path):
                    self.db.delete_image(path) #Wipe old tags
                    self.ai_engine.queue_image(path) #Re-queue
                    
            QMessageBox.information(self, "Re-Tagging Started", f"Sent {len(all_images)} images to the AI queue.") 
            
    def remove_folder(self, item, permanent=False):
        data = item.data(0, Qt.ItemDataRole.UserRole)
        if not isinstance(data, dict) or data.get("type") != "physical": return
        
        path = data.get("path")
        
        #Ensure path is  a string
        if not path or not isinstance(path, str): 
            return
            
        if permanent:
            reply = QMessageBox.question(self, "Permanent Delete", 
                f"Are you sure you want to PERMANENTLY delete the folder '{os.path.basename(path)}' and ALL its images from your PC?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
            if reply != QMessageBox.StandardButton.Yes: return

        self.db.delete_folder(path) 
        
        if self.current_folder_path == path:
            self.canvas.grid.clear() 
            self.current_folder_path = None 
            self.canvas.stack.setCurrentWidget(self.canvas.welcome_screen) 
            
        if permanent:
            try:
                import shutil
                shutil.rmtree(path)
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Could not delete folder from hard drive.\n\n{e}")
        self.refresh_sidebar()
    
    
     #sidebar with visual heirarchy   
    def refresh_sidebar(self):
        
        expanded_paths = set()
        
        # If this is the first load (empty tree), load from settings
        if self.folder_list.topLevelItemCount() == 0:
            saved_folders = self.settings.get("expanded_folders", [])
            for data in saved_folders:
                if isinstance(data, dict):
                    if data.get("type") == "physical" and "path" in data:
                        expanded_paths.add(data["path"])
                    elif data.get("type") == "smart" and "query" in data:
                        expanded_paths.add(data["query"])
                elif isinstance(data, str): 
                    # Fallback just in case older V1 settings are still in the JSON
                    expanded_paths.add(data)
        else:
            # Otherwise, save current state before refreshing
            iterator = QTreeWidgetItemIterator(self.folder_list)
            while iterator.value():
                tree_item = iterator.value()
                if tree_item and tree_item.isExpanded():
                    data = tree_item.data(0, Qt.ItemDataRole.UserRole)
                    if isinstance(data, dict):
                        if data.get("type") == "physical" and "path" in data:
                            expanded_paths.add(data["path"])
                        elif data.get("type") == "smart" and "query" in data:
                            expanded_paths.add(data["query"])
                iterator += 1
        #Save scroll position
        v_scrollbar = self.folder_list.verticalScrollBar()
        scroll_pos = v_scrollbar.value() if v_scrollbar else 0
            
        self.folder_list.clear()
        
        #Load Smart Folders (Top of the list) 
        smart_folders = self.db.get_smart_folders()
        if smart_folders:
            smart_header = QTreeWidgetItem(["Smart Collections"])
            smart_header.setIcon(0, QIcon("icons/smart_folder.png"))
            smart_header.setExpanded(True)
            self.folder_list.addTopLevelItem(smart_header)
            
            for name, query in smart_folders:
                item = QTreeWidgetItem([name])
                item.setData(0, Qt.ItemDataRole.UserRole, {"type": "smart", "query": query})
                item.setToolTip(0, f"Query: {query}")
                item.setIcon(0, self.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogDetailedView)) #type:ignore
                smart_header.addChild(item)

        #Load Physical Folders (Below Smart Folders)
        phys_header = QTreeWidgetItem(["Local Vault"])
        phys_header.setExpanded(True)
        self.folder_list.addTopLevelItem(phys_header)
        
        saved_folders = self.db.get_folders()
        item_map = {}
        custom_hierarchy = self.settings.get("custom_hierarchy", {})
        
        # Pass 1: Create all visual items and map them by their clean path
        for name, path in saved_folders:
            clean_path = os.path.normpath(path)
            
            item = QTreeWidgetItem([name])
            item.setData(0, Qt.ItemDataRole.UserRole, {"type": "physical", "path": path})
            item.setToolTip(0, path)
            item.setIcon(0, self.style().standardIcon(QStyle.StandardPixmap.SP_DirIcon)) #type:ignore
            
            item_map[clean_path] = item
            
        # Pass 2: Connect parents and children using the visual overrides
        for name, path in saved_folders:
            clean_path = os.path.normpath(path)
            item = item_map[clean_path]
            
            # Check if user dragged this folder manually, otherwise fallback to true OS parent
            if path in custom_hierarchy:
                parent_key = custom_hierarchy[path]
            else:
                parent_key = os.path.dirname(clean_path)
                
            # Attach the visual item to its respective parent
            if parent_key == "root":
                phys_header.addChild(item)
            elif parent_key in item_map:
                item_map[parent_key].addChild(item)
            else:
                # Fallback to the top level if the parent folder was deleted from DB
                phys_header.addChild(item)
            
        #Restore expanded state
        item_to_select = None
        restore_iterator = QTreeWidgetItemIterator(self.folder_list)
        while restore_iterator.value():
            tree_item = restore_iterator.value()
            if tree_item:
                data = tree_item.data(0, Qt.ItemDataRole.UserRole)
                if isinstance(data, dict):
                    # Restore expansion
                    if data.get("type") == "physical" and data.get("path") in expanded_paths:
                        tree_item.setExpanded(True)
                    elif data.get("type") == "smart" and data.get("query") in expanded_paths:
                        tree_item.setExpanded(True)
                    
                    #Restore selection highlight visually
                    if data.get("path") == self.current_folder_path:
                        item_to_select = tree_item
            restore_iterator += 1
            
        if item_to_select:
            self.folder_list.setCurrentItem(item_to_select)
            
        #Restore exact scroll position
        if v_scrollbar:
            v_scrollbar.setValue(scroll_pos)
    
    #add folder to sidebar when dropped and store full path in item data for later use
    def add_folder_to_sidebar(self, folder_name, full_path):
        self.db.add_folder(folder_name, full_path) #save to database
        
        #Update tracker and force the UI to rebuild the tree
        self.current_folder_path = full_path
        self.refresh_sidebar()
        
        #Load the images into the canvas
        self.search_bar.setEnabled(True)
        self.search_bar.clear()
        self.canvas.load_images_from_path(full_path)
        
        #Tell crawler to scan the newly dropped folder
        self.start_crawler([full_path])
    
    
    def handle_folder_move(self, dragged_item, target_item):
        import json
        
        drag_data = dragged_item.data(0, Qt.ItemDataRole.UserRole)
        target_data = target_item.data(0, Qt.ItemDataRole.UserRole)
        
        # Ensure we are only moving physical folders
        if not isinstance(drag_data, dict) or drag_data.get("type") != "physical":
            return 
            
        drag_path = drag_data.get("path")
        
        # Type Guard: Fixes Pylance Unknown | None errors
        if not drag_path or not isinstance(drag_path, str): 
            return
        
        # Determine the visual target
        if isinstance(target_data, dict) and target_data.get("type") == "physical":
            target_path = target_data.get("path")
            if not target_path or not isinstance(target_path, str): return
            target_key = os.path.normpath(target_path)
        elif target_item.text(0) == "Local Vault":
            target_key = "root"
        else:
            return 
            
        # Initialize dictionary if it doesn't exist yet
        if "custom_hierarchy" not in self.settings:
            self.settings["custom_hierarchy"] = {}
            
        # Prevent dragging into itself
        if os.path.normpath(drag_path) == target_key:
            return

        # Save the visual override
        self.settings["custom_hierarchy"][drag_path] = target_key
        
        # Save to disk so it persists reboots
        try:
            with open(self.settings_path, "w") as f:
                json.dump(self.settings, f)
        except Exception as e:
            print(f"Failed to save visual layout: {e}")
            
        self.refresh_sidebar()
       
    #when a folder is clicked in the sidebar, load its images in the canvas
    def on_sidebar_folder_clicked(self, item):
        data = item.data(0, Qt.ItemDataRole.UserRole)
        if not data: return # Clicked a header
        
        if data["type"] == "physical":
            folder_path = data["path"]
            if folder_path != self.current_folder_path: 
                self.current_folder_path = folder_path
                self.search_bar.setEnabled(True)
                self.search_bar.clear()
                self.canvas.load_images_from_path(folder_path)
                
        elif data["type"] == "smart":
            query = data["query"]
            self.current_folder_path = None #Detach from physical folder
            self.search_bar.setEnabled(True)
            self.search_bar.setText(query) #Automatically fill the search bar
            
            # Execute the smart query visually
            matching_paths = self.db.global_search_by_tag(query)
            self.canvas.load_images_from_list(matching_paths)
    
    #shutdown function stops the AI and threads
    def closeEvent(self,event): #type:ignore
        print("Saving UI state and shutting down...")
        
        # Traverse tree to find expanded folders
        expanded = []
        iterator = QTreeWidgetItemIterator(self.folder_list)
        while iterator.value():
            item = iterator.value()
            if item is not None and item.isExpanded(): 
                expanded.append(item.data(0, Qt.ItemDataRole.UserRole))
            iterator += 1
            
        self.settings["expanded_folders"] = expanded
        self.settings["last_folder"] = self.current_folder_path #save last viewed folder
        with open(self.settings_path, "w") as f:
            json.dump(self.settings, f)
            
        self.canvas.stop_threads()
        self.ai_engine.stop_engine()
        event.accept()   
        
    #get the signal and keep it in RAM   
    def save_generated_tags(self,image_path,tags_list):
        self.tag_buffer.append((image_path, tags_list))
    
    #process buffer every 2 seconds    
    def process_tag_buffer(self):
        if not self.tag_buffer:
            return
            
        #save the current batch and clear the list so the AI can keep working
        batch_to_process = self.tag_buffer[:]
        self.tag_buffer.clear()
        
        #save to DB in one big chunk
        self.db.batch_add_tags(batch_to_process)
        
        #safely update the UI tooltips in bulk
        for image_path, tags_list in batch_to_process:
            self.update_image_tooltip(image_path, tags_list)
            
        #rebuild the search autocomplete ONLY once per batch, not per image
        self.update_search_autocomplete()
        print(f"Batch saved {len(batch_to_process)} images to database smoothly.")
     
        
    
    def update_image_tooltip(self, image_path, tags_list):
        #Finds the tagged image in the UI grid and updates its hover text
        
        #Format the tags
        chunked_tags = [", ".join(tags_list[i:i+5]) for i in range(0, len(tags_list), 5)]
        tag_string = ",\n".join(chunked_tags)
        new_tooltip = f"{os.path.basename(image_path)}\nTags:\n{tag_string}"
        
        #Loop through the visual grid to find the matching thumbnail
        for i in range(self.canvas.grid.count()):
            item = self.canvas.grid.item(i)
            #Check if this thumbnail's saved path matches the one the AI just finished
            if item is not None and item.data(Qt.ItemDataRole.UserRole) == image_path:
                item.setToolTip(new_tooltip)
                break #Stop searching once updated it    
    
    #function starts the crawler
    def start_crawler(self,folder_paths_list):        
        self.crawler  = BackgroundCrawlerThread(folder_paths_list,self.db)
        
        #Route crawler discoveries directly to the AI inbox
        self.crawler.untagged_image_found.connect(self.ai_engine.queue_image)
        self.crawler.start()
        
    #search with search bar
    def perform_search(self,text):
         
        
        search_term=text.strip().lower()
        
        #if user deletes thier search or types only spaces then show all images
        if not search_term:
            if self.current_folder_path:
                #use Tree Iterator to reselect the folder visually ---
                iterator = QTreeWidgetItemIterator(self.folder_list)
                while iterator.value():
                    item = iterator.value()
                   
                    if item.data(0, Qt.ItemDataRole.UserRole) == self.current_folder_path: #type:ignore
                        self.folder_list.setCurrentItem(item)
                        break
                    iterator += 1
                #reload the folder's images
                self.canvas.load_images_from_path(self.current_folder_path)
            else:
                self.canvas.grid.clear()
                self.canvas.stack.setCurrentWidget(self.canvas.welcome_screen)
            return        
            
        
        #ask db for global paths that match the tag
        matching_paths = self.db.global_search_by_tag(search_term)
        #Deselect sidebar visually
        #need to remember where they were so we can return when they clear the search bar
        self.folder_list.clearSelection()
        self.canvas.load_images_from_list(matching_paths)
        
        
    def on_ai_ready(self):
        #clear loading text
        self.search_bar.clear()
        self.search_bar.setPlaceholderText("Search for images here (e.g. 'girl','sword','dynamic pose')...")
        
        if self.current_folder_path:
            self.search_bar.setEnabled(True)    
        self.update_search_autocomplete() #learn new words in real time as ai tags
        print("UI unlocked,ready for search")    
        
    def update_search_autocomplete(self):
        #fetch all known tags from db and give to the search bar
        tags = self.db.get_unique_tags()
        model= QStringListModel(tags)
        self.completer.setModel(model)
    
    
    def open_lightbox(self,item):
        from ui.lightbox import AdvancedLightbox
        #get file path attatched to a image that is double clicked by the user
        image_path = item.data(Qt.ItemDataRole.UserRole)
        
        if image_path and os.path.exists(image_path):
            #Close old lightbox if one is already open
            if hasattr(self, 'lightbox') and self.lightbox:
                self.lightbox.close()
            
            #Spawn non-modally and keep a reference so it doesn't get garbage collected
            self.lightbox =AdvancedLightbox(parent_grid=self.canvas.grid, starting_item=item, parent=self)
            self.lightbox.show()       
    
    def show_help(self):
        QMessageBox.information(
            self,
            "Vault Controls & Help",
            "Welcome to Reference Vault v2!\n\n"
            "🔍 SEARCH ENGINE & AI:\n"
            "• Use '+' or '-' to include/exclude tags (e.g., 'sword -blood').\n"
            "• Auto-Tagger queues images in the background. Use the top-left buttons to Pause/Clear the queue.\n\n"
            "📂 LIBRARY MANAGEMENT:\n"
            "• Drag & Drop folders inside the sidebar to visually organize them (does not move OS files).\n"
            "• Right-click folders to Re-tag, Rename, or create Smart Collections.\n\n"
            "🎞️ ADVANCED LIGHTBOX (Double-click image):\n"
            "• [V] Toggle Grayscale | [M] Mirror horizontally.\n"
            "• [,] and [.] Step frame-by-frame through MP4/GIFs.\n"
            "• [Shift+Click & Drag] Crop and save a detail shot.\n\n"
            "🎨 INFINITE MOODBOARD (PureRef Mode):\n"
            "• Right-click grid images -> 'Send to Moodboard'.\n"
            "• Click images to reveal 8 resize handles (corners scale proportionally, edges stretch).\n"
            "• Right-click an image on the board to 'Restore 1:1 Original Size'.\n"
            "• [Middle-Click / Alt+Click] Pan the camera.\n\n"
            "⏱️ GESTURE PRACTICE:\n"
            "• Click 'Gesture Practice' to start a timed figure-drawing session from your vault."
        )        
        
    def update_ai_status(self, count=None):
        # If called without a specific count (like from a button click), just check the queue directly
        if not isinstance(count, int):
            count = self.ai_engine.inbox.qsize()

        is_paused = getattr(self.ai_engine, 'is_paused', False)

        # Disable buttons entirely if queue is empty
        self.stop_ai_btn.setEnabled(count > 0)
        self.pause_ai_btn.setEnabled(count > 0 or is_paused)

        # 1. Determine Engine Memory State
        if self.ai_engine.session is not None:
            engine_text = "🤖 AI: Loaded (Ready)"
            base_color = "#2ecc71" # Green
        else:
            engine_text = "💤 AI: Unloaded"
            base_color = "#95a5a6" # Gray

        # 2. Determine Queue State
        if count > 0:
            if is_paused:
                queue_text = f"⏸ Queue: {count} (Paused)"
                base_color = "#f39c12" # Orange overrides memory color if paused
            else:
                queue_text = f"⚙️ Queue: {count} left"
                base_color = "#f1c40f" # Yellow overrides memory color if actively working
        else:
            queue_text = "📋 Queue: 0"

        # Apply the combined 2-line text
        self.ai_status_label.setText(f"{engine_text}\n{queue_text}")
        self.ai_status_label.setStyleSheet(f"""
            color: {base_color}; 
            padding: 8px; 
            font-weight: bold; 
            background-color: #273746; 
            border-radius: 5px;
        """)
    
    
    
    
     #Displays a popup when a new GitHub release is found.
    def show_update_dialog(self, latest_version, release_url):
       
        reply = QMessageBox.information(
            self,
            "Update Available!",
            f"A new version of Reference Vault ({latest_version}) is available!\n\n"
            f"You are currently running {self.CURRENT_VERSION}.\n\n"
            f"Would you like to download the update now?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            #Opens the users default web browser (Chrome/Edge/etc) to the download page
            QDesktopServices.openUrl(QUrl(release_url))         
    #spawns a right-click menu when clicking an image in the grid      
          
    def on_image_context_menu(self, pos):
        item = self.canvas.grid.itemAt(pos)
        if item is None:
            return

        # Handle multi-selection: if they right-click an unselected item, select only that item
        if not item.isSelected():
            self.canvas.grid.clearSelection()
            item.setSelected(True)
            
        selected_items = self.canvas.grid.selectedItems()
        selected_count = len(selected_items)

        menu = QMenu(self)
        menu.setStyleSheet("background-color: #34495e; color: white; padding: 5px;")
        
        #Added Send to Moodboard action
        send_board_action = menu.addAction(f"Send {selected_count} Image(s) to Moodboard")
        menu.addSeparator()
        
        # Only show "Edit Tags" if a single image is selected
        edit_tags_action = None
        if selected_count == 1:
            edit_tags_action = menu.addAction("Edit Tags")
            menu.addSeparator()
            
        remove_ref_action = menu.addAction(f"Remove {selected_count} Reference(s) from Vault")
        delete_perm_action = menu.addAction(f"Delete {selected_count} File(s) Permanently from PC")

        #spawn the menu exactly where the mouse is
        action = menu.exec(self.canvas.grid.viewport().mapToGlobal(pos)) #type:ignore
        
        if action == send_board_action:
            for selected_item in selected_items:
                path = selected_item.data(Qt.ItemDataRole.UserRole)
                self.moodboard.board.add_image(path)
            self.moodboard.show() #Auto-show the board so the user sees it arrived
        elif edit_tags_action and action == edit_tags_action:
            self.edit_image_tags(item)
        elif action == remove_ref_action:
            self.delete_selected_images(selected_items, permanent=False)
        elif action == delete_perm_action:
            self.delete_selected_images(selected_items, permanent=True)


    def delete_selected_images(self, items_to_delete, permanent=False):
        if permanent:
            reply = QMessageBox.question(
                self,
                "Delete Images",
                f"Are you sure you want to PERMANENTLY delete {len(items_to_delete)} file(s) from your hard drive?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
        #Setup a safe "Eviction" folder in the user's Documents for soft-deleted files
        removed_dir = os.path.join(str(Path.home()), "Documents", "ReferenceVault_Removed")
        if not permanent:
            os.makedirs(removed_dir, exist_ok=True)
        # Iterate backwards so removing items from the UI doesn't shift the index
        for item in reversed(items_to_delete):
            image_path = item.data(Qt.ItemDataRole.UserRole)
            
            #Delete from Database
            try:
                self.db.delete_image(image_path) 
            except AttributeError:
                print("Warning: delete_image method missing in database.py")
                
            #Delete from Windows Hard Drive
            if permanent:
                try:
                    os.remove(image_path)
                except Exception as e:
                    print(f"Error permanently deleting file {image_path}: {e}")
            else:
                #MOVE the file completely out of the monitored Vault folder
                try:
                    filename = os.path.basename(image_path)
                    dest_path = os.path.join(removed_dir, filename)
                    
                    #If user already removed a file with this exact name, add a random string so it doesn't overwrite
                    if os.path.exists(dest_path):
                        import uuid
                        name, ext = os.path.splitext(filename)
                        dest_path = os.path.join(removed_dir, f"{name}_{uuid.uuid4().hex[:6]}{ext}")
                    
                    shutil.move(image_path, dest_path)
                except Exception as e:
                    print(f"Error moving file out of vault {image_path}: {e}")
                    
            #Delete from UI visually
            row = self.canvas.grid.row(item)
            self.canvas.grid.takeItem(row)

    def edit_image_tags(self, item):
        """Pulls current tags, lets the user edit them, and saves to DB."""
        image_path = item.data(Qt.ItemDataRole.UserRole)
        
        #get current tags from DB and convert to a comma-separated string
        current_tags = self.db.get_tags_for_image(image_path)
        current_tags_str = ", ".join(current_tags)
        
        #spawn popup window
        new_tags_str, ok = QInputDialog.getText(
            self, 
            "Edit Image Tags", 
            "Edit tags (comma separated):", 
            text=current_tags_str
        )
        
        if ok:
            #clean up the user's input (remove extra spaces and make lowercase)
            raw_tags = new_tags_str.split(',')
            new_tags = [t.strip().lower() for t in raw_tags if t.strip()]
            
            #update Database
            self.db.update_image_tags(image_path, new_tags)
            
            #update the hover Tooltip visually
            self.update_image_tooltip(image_path, new_tags)
            self.update_search_autocomplete()
            
    #This function warns the user then deletes all existing tags for that folder from the database
    #loops through the folder and puts the images back into the Ai's queue        
    def retag_folder(self, folder_path):
        reply = QMessageBox.question(
            self,
            "Re-Tag Folder",
            "This will clear all current tags (including manual ones) for images in this folder and send them back to the AI.\n\nDo you want to proceed?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            valid_extensions = ['.jpg', '.jpeg', '.png', '.bmp', '.webp']
            images_queued = 0
            
            #find all images in this folder (and its subfolders)
            for root, dirs, files in os.walk(folder_path):
                for file in files:
                    if os.path.splitext(file)[1].lower() in valid_extensions:
                        full_path = os.path.join(root, file)
                        
                        #wipe the old tags from the Database
                        try:
                            self.db.delete_image(full_path)
                        except AttributeError:
                            pass
                            
                        #queue it back into the AI engine
                        self.ai_engine.queue_image(full_path)
                        images_queued += 1
                        
            if images_queued > 0:
                print(f"Sent {images_queued} images to the AI Tagger.")
                
                #refresh the visual canvas to clear the tooltips immediately
                if self.current_folder_path and self.current_folder_path.startswith(folder_path):
                    self.canvas.load_images_from_path(self.current_folder_path)
            else:
                QMessageBox.information(self, "Empty", "No valid images found in this folder.")
    
    
    def on_ai_loaded(self):
        self.toggle_ai_btn.setText("🛑 Unload Tagger")
        self.toggle_ai_btn.setStyleSheet("background-color: #c0392b; color: white; border-radius: 4px; padding: 8px; font-weight: bold;")
        self.update_ai_status() # Refresh dual-label
        
        
    


    def on_ai_unloaded(self):
        self.toggle_ai_btn.setText("▶️ Load Tagger")
        self.toggle_ai_btn.setStyleSheet("background-color: #2ecc71; color: white; border-radius: 4px; padding: 8px; font-weight: bold;")
        self.update_ai_status() # Refresh dual-label           
    #wipe cache
    def action_clear_cache(self):
        reply = QMessageBox.question(
            self, "Clear Cache", 
            "Are you sure you want to delete all cached thumbnails?\nThis frees disk space, but folders will load slower the next time you open them.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.cache_manager.clear_cache()
            QMessageBox.information(self, "Success", "Thumbnail cache cleared.")    
            
    def save_current_search_as_smart_folder(self):
        """Connect this to a '+' button next to the search bar"""
        current_query = self.search_bar.text().strip()
        if not current_query: return
        
        name, ok = QInputDialog.getText(self, "New Smart Folder", "Enter a name for this collection:")
        if ok and name.strip():
            self.db.add_smart_folder(name.strip(), current_query)
            self.refresh_sidebar()        
            
    def toggle_ai_pause(self):
        is_paused = self.ai_engine.toggle_pause()
        if is_paused:
            self.pause_ai_btn.setText("▶ Resume Queue")
            self.pause_ai_btn.setStyleSheet("""
                QPushButton { background-color: #2ecc71; color: white; border-radius: 4px; padding: 5px; }
                QPushButton:disabled { background-color: #555555; color: #888888; }
            """)
        else:
            self.pause_ai_btn.setText("⏸ Pause Queue")
            self.pause_ai_btn.setStyleSheet("""
                QPushButton { background-color: #f39c12; color: white; border-radius: 4px; padding: 5px; }
                QPushButton:disabled { background-color: #555555; color: #888888; }
            """)
        self.update_ai_status() # Instantly update label to show "Paused" state

    def handle_new_image(self, image_path):
        if self.settings.get("auto_tag_import", True):
            self.ai_engine.queue_image(image_path)

    def start_gesture_mode(self):
        from gesture_mode import GestureSetupDialog, GestureSession
        dialog = GestureSetupDialog(self.db, self)
        if dialog.exec():
            if dialog.selected_images:
                # Safely get the limit from the dialog, default to None if missing
                session_limit = getattr(dialog, 'session_time_limit', None)
                # Pass arguments exactly in order
                self.gesture_session = GestureSession(dialog.selected_images, dialog.time_limit, session_limit, self)
                self.gesture_session.show()
            else:
                QMessageBox.warning(self, "Empty", "No valid images found in the selected folders.")

    def action_cache_all(self):
        # Force cache generation for all uncached vault images
        from ui.canvas import ImageLoaderThread
        from PyQt6.QtWidgets import QProgressDialog
        
        #Gather all actual image files from the saved folders
        all_files = []
        for name, folder in self.db.get_folders():
            if not os.path.exists(folder): continue
            for root, _, files in os.walk(folder):
                for file in files:
                    if os.path.splitext(file)[1].lower() in self.canvas.valid_extensions:
                        all_files.append(os.path.join(root, file))
                        
        if not all_files:
            QMessageBox.information(self, "Empty", "No valid images found to cache.")
            return
            
        #Feed the raw files to the background thread
        self.caching_thread = ImageLoaderThread(all_files, self.canvas.valid_extensions)
        
        #Create a visual Progress Dialog (Indeterminate Marquee)
        self.cache_dialog = QProgressDialog("Caching Vault Images in the background...\nThis may take a while for large vaults.", "Cancel", 0, 0, self)
        self.cache_dialog.setWindowTitle("Global Caching")
        self.cache_dialog.setStyleSheet("background-color: #2a2a2a; color: white; QLabel { color: white; }")
        self.cache_dialog.setWindowModality(Qt.WindowModality.WindowModal)
        self.cache_dialog.setMinimumDuration(0)
        
        # Connect Cancel button to kill the thread, and thread finish to close the dialog
        self.cache_dialog.canceled.connect(self.caching_thread.requestInterruption)
        self.caching_thread.finished.connect(self.cache_dialog.accept)
        
        self.caching_thread.start()
        self.cache_dialog.show()
        
        