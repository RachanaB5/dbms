from app import app, db
from models import User
from werkzeug.security import generate_password_hash

with app.app_context():
    admin = User(
        name='Admin',
        email='admin@example.com',  # Change to your desired admin email
        phone='',
        password_hash=generate_password_hash('admin@123'),  # Change to your desired password
        is_admin=True
    )
    db.session.add(admin)
    db.session.commit()
    print("Admin user created!")