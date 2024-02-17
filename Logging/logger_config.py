import logging

def configure_logging():
    log_format = '%(asctime)s [%(levelname)s] - %(message)s'
    
    file_handler = logging.FileHandler('app.log')
    file_handler.setLevel(logging.WARNING)
    file_handler.setFormatter(logging.Formatter(log_format))

    logging.getLogger().addHandler(file_handler)

logger = logging.getLogger(__name__)