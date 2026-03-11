import sys
import PyQt6 
from PyQt6.QtWidgets import QApplication,QMainWindow,QLabel,QVBoxLayout,QWidget,QHBoxLayout,QPushButton,QFrame,QLabel

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
        
        #add sidebar and canvas to main layout
        main_layout.addWidget(self.sidebar)
        main_layout.addWidget(self.canvas)
        
        

if __name__ == "__main__":
    #loop to run the application
    app = QApplication(sys.argv)
    window = ReferenceVaul()
    window.show()
    sys.exit(app.exec())        