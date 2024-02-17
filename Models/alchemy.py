from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.exc import IntegrityError
from Logging import configure_logging, logger

db = SQLAlchemy()

configure_logging()

def commit():
    try:
        db.session.commit()
    except IntegrityError as e:
        db.session.rollback()
        logger.error(f"Error: {str(e)}")