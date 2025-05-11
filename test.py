from app import app, db
from models import User
from werkzeug.security import generate_password_hash

with app.app_context():
    # First admin
    admin1 = User(
        username='Rachana',  # Changed from name to username
        email='rachana@gmail.com',
        phone='',
        password_hash=generate_password_hash('12345678'),
        is_admin=True
    )
    
    # Second admin
    admin2 = User(
        username='Priyanshu',  # Changed from name to username
        email='priyanshu@gmail.com',
        phone='',
        password_hash=generate_password_hash('98765432'),
        is_admin=True
    )
    
    # Add both admins
    db.session.add(admin1)
    db.session.add(admin2)
    db.session.commit()
    print("Both admin users created successfully!")
    
