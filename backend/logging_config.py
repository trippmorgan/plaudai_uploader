"""
PlaudAI Uploader - Central Logging Configuration
"""
import logging
import logging.handlers
import os
import sys
from pathlib import Path
from .config import LOG_LEVEL, LOG_FILE, BASE_DIR

def configure_logging():
    """
    Setup detailed logging configuration
    - Rotates logs every 10MB (keeps 5 backups)
    - detailed formatting with timestamps
    - Separate handling for errors vs info
    """
    
    # Ensure log directory exists
    log_path = Path(BASE_DIR) / LOG_FILE
    log_dir = log_path.parent
    os.makedirs(log_dir, exist_ok=True)

    # Define Formatters
    detailed_formatter = logging.Formatter(
        fmt='%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    console_formatter = logging.Formatter(
        fmt='%(levelname)s: %(message)s'
    )

    # 1. File Handler (Rotating)
    file_handler = logging.handlers.RotatingFileHandler(
        filename=log_path,
        maxBytes=10 * 1024 * 1024,  # 10 MB
        backupCount=5,
        encoding='utf-8'
    )
    file_handler.setFormatter(detailed_formatter)
    file_handler.setLevel(getattr(logging, LOG_LEVEL))

    # 2. Console Handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(console_formatter)
    console_handler.setLevel(logging.INFO)

    # 3. Root Logger Setup
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, LOG_LEVEL))
    
    # Remove existing handlers to avoid duplicates during reloads
    if root_logger.hasHandlers():
        root_logger.handlers.clear()
        
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)

    # 4. Third-party loggers (Quiet them down)
    logging.getLogger("uvicorn.access").handlers = []  # Disable default uvicorn access logs (we will add our own)
    logging.getLogger("multipart").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)

    logging.info(f"✅ Logging initialized. Writing to: {log_path}")