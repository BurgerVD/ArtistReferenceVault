#controller for the main canvas area where images are displayed. It also handles drag and drop of folders to add them to the vault.
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QListWidgetItem, QMainWindow,QVBoxLayout,QStackedWidget,QLabel,QListWidget, QWidget
from PyQt6.QtCore import Qt
from canvas import DropCanvas

#this class is the main window of the application. It contains the sidebar and the canvas. It listens for signals from the canvas when a folder is dropped and adds it to the sidebar. It also handles clicks on the sidebar to load the corresponding images in the canvas.
class ReferenceVaul(QMainWindow):
    def __init__(self):
        super().__init__()
        self.current_folder_path = None #track the currently loaded folder path to avoid reloading if the same folder is clicked again
        #main window
        self.setWindowTitle("Reference Vault")
        self.resize(1000,700)
        
        #central contaainer and horizontal layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        
        #remove margins and spacing
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        #sidebar for folders and tags
        self.sidebar=QFrame()
        self.sidebar.setFixedWidth(250)
        self.sidebar.setStyleSheet("background-color: #2c3e50;color: white;")
        sidebar_layout = QVBoxLayout(self.sidebar)
        #list for folders
        self.folder_list=QListWidget()
        self.folder_list.setStyleSheet("QListWidget{border: none;font-size:14px;QListWidget::item{padding:10px;QListWidget::item:selected{background-color:#34495e;}}}")
        #connect folder click to load images in canvas
        self.folder_list.itemClicked.connect(self.on_sidebar_folder_clicked)
        
        sidebar_layout.addWidget(self.folder_list)

        #add drop canvas for image grid
        self.canvas = DropCanvas()
        self.canvas.folder_dropped.connect(self.add_folder_to_sidebar)
        
        main_layout.addWidget(self.sidebar)
        main_layout.addWidget(self.canvas) 
    
    #add folder to sidebar when dropped and store full path in item data for later use
    def add_folder_to_sidebar(self, folder_name, full_path):
        item = QListWidgetItem(folder_name)
        #store the full path in the item data for later use when clicked
        item.setData(Qt.ItemDataRole.UserRole, full_path) 
        self.folder_list.addItem(item) 
        
        #when a folder is added, automatically load it in the canvas and switch to canvas view
        if self.folder_list.count()==1:
          
            #select and load first folder and update the tracker
            self.folder_list.setCurrentItem(item)
            self.current_folder_path = full_path
            self.canvas.load_images_from_path(full_path)
           
   
       
    #when a folder is clicked in the sidebar, load its images in the canvas
    def on_sidebar_folder_clicked(self, item):
        folder_path = item.data(Qt.ItemDataRole.UserRole) #get full path from item data
        if folder_path != self.current_folder_path: #only reload if different folder is clicked
            self.current_folder_path = folder_path
        self.canvas.load_images_from_path(folder_path)
       