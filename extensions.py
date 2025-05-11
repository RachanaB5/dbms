from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
import os

# Initialize extensions with custom configuration
db = SQLAlchemy()
login_manager = LoginManager()

def init_db(app):
    try:
        # Configure database
        app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql://root:Rachana@05@localhost:3306/EcommerceDB'
        app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
        app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
            'pool_recycle': 3600,
            'pool_timeout': 30,
            'pool_size': 10
        }
        
        # Initialize database
        db.init_app(app)
        with app.app_context():
            db.create_all()
            
    except Exception as e:
        print(f"Database Error: {e}")
        raise
