# Move the database initialization to a separate file to avoid circular imports
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()