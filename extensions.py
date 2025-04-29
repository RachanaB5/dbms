# Move the database initialization and login manager to a separate file to avoid circular imports
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager

db = SQLAlchemy()
login_manager = LoginManager()