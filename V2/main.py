import sys
import logging
from PyQt5.QtWidgets import QApplication
from PyQt5.QtGui import QFont

from ui.main_window import UEProjectUploader
from core.constants import LOG_FORMAT

def configure_logging():
    """Configure logging for the application"""
    logging.basicConfig(
        level=logging.INFO,
        format=LOG_FORMAT,
        handlers=[
            logging.FileHandler("ue_github_pusher.log"),
            logging.StreamHandler()
        ]
    )

def main():
    """Main application entry point"""
    configure_logging()
    
    app = QApplication(sys.argv)
    app.setStyle('Fusion')  # Modern style
    
    # Set application font
    font = QFont()
    font.setFamily("Segoe UI")
    font.setPointSize(10)
    app.setFont(font)
    
    window = UEProjectUploader()
    window.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()