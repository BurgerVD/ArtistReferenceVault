import sys
from PyQt6.QtWidgets import QApplication
from window import ReferenceVaul



#entry point of the application. It creates the main window and starts the event loop.
if __name__ == "__main__":
    #loop to run the application
    app = QApplication(sys.argv)
    window = ReferenceVaul()
    window.show()
    sys.exit(app.exec())        