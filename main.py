
import os
import sys
import ctypes

from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QIcon
from window import ReferenceVault

#entry point of the application
if __name__ == "__main__":
    try:
        myappid='burger.referencevault.app.1.0'
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid) #type:ignore
    except Exception as e:
        pass
    #loop to run the application
    
    
    app = QApplication(sys.argv)
    #window icon fix
    icon_path = os.path.join(os.getcwd(), "app_icon.ico")
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))
    window = ReferenceVault()
    window.show()
    sys.exit(app.exec())        