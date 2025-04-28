from extensions import db  # Import db from extensions
from datetime import datetime  # Import datetime module
from flask_login import UserMixin  # Import UserMixin for Flask-Login support

# Define your models here
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    phone = db.Column(db.String(15), nullable=True)
    password_hash = db.Column(db.String(256), nullable=False)
    _is_admin = db.Column('is_admin', db.Boolean, default=False)

    @property
    def is_admin(self):
        return self._is_admin

class Product(db.Model):
    __tablename__ = 'products'
    id = db.Column('product_id', db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=True)
    price = db.Column(db.Float, nullable=False)
    category = db.Column(db.String(50), nullable=True)
    image = db.Column(db.String(100), nullable=True)
    discount = db.Column(db.Integer, nullable=True, default=0)  # percent discount
    stock_quantity = db.Column(db.Integer, nullable=False, default=0)
    reviews = db.relationship('Review', backref='product', lazy=True, foreign_keys='Review.product_id')

class Review(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('products.product_id'), nullable=False)
    rating = db.Column(db.Integer, nullable=False)
    review_text = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    helpful_count = db.Column(db.Integer, default=0)
    user = db.relationship('User', backref='reviews')

class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class OrderItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('order.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('products.product_id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
