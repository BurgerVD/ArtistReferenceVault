import sys
import PyQt6 
from PyQt6.QtWidgets import QApplication,QMainWindow,QLabel,QVBoxLayout,QWidget,QHBoxLayout,QPushButton,QFrame,QLabel
from PyQt6.QtCore import Qt

#drag and drop images onto the canvas to add them to the vault
class DropCanvas(QFrame):
    #canvas for image grid
    def __init__(self):
        super().__init__()
        self.setStyleSheet("background-color: #1e1e1e;color: gray;")
        self.setAcceptDrops(True)
        
        layout=QVBoxLayout(self)
        self.label=QLabel("Drag and drop images here to add to vault")
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.label)
    
    #handle drag enter event
    def dragEnterEvent(self, event): # type: ignore
        #accept the event if it contains urls (files)
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self.setStyleSheet("background-color: #2a2a2a;color: white;")
        else:
            event.ignore()
    
    #If the user drags the item out of the canvas, reset the style
    def dragLeaveEvent(self, event): # type: ignore
        self.setStyleSheet("background-color: #1e1e1e;color: gray;")            
        
    #triggered when the user drops files onto the canvas
    def dropEvent(self, event): # type: ignore
        self.setStyleSheet("background-color: #1e1e1e;color: gray;")
        for url in event.mimeData().urls():
            file_path=url.toLocalFile()
            print(f"File dropped: {file_path}")
            self.label.setText(f"Added: {file_path.split('/')[-1]}")  # Display the name of the added file
    
class ReferenceVaul(QMainWindow):
    def __init__(self):
        super().__init__()
        
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
        sidebar_layout.addWidget(QLabel("Folders & tags"))
        
        #canvas for image grid
        self.canvas=QFrame()
        self.canvas.setStyleSheet("background-color: #1e1e1e;color: gray;")
        
        canvas_layout = QVBoxLayout(self.canvas)
        canvas_layout.addWidget(QLabel("Image Grid thumbnails here"))
        
        #add drag and drop canvas
        self.canvas=DropCanvas()
        
        #add sidebar and canvas to main layout
        main_layout.addWidget(self.sidebar)
        main_layout.addWidget(self.canvas)
        
        

if __name__ == "__main__":
    #loop to run the application
    app = QApplication(sys.argv)
    window = ReferenceVaul()
    window.show()
    sys.exit(app.exec())        