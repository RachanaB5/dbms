from extensions import db
from flask_login import UserMixin
from datetime import datetime
from decimal import Decimal
from flask import url_for  # Add this import at the top
from utils.encryption import hash_card_number, get_last_four_digits

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    phone = db.Column(db.String(15))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_admin = db.Column(db.Boolean, default=False)

    def __init__(self, username, email, password_hash, phone=None, is_admin=False):
        self.username = username
        self.email = email
        self.password_hash = password_hash
        self.phone = phone
        self.is_admin = is_admin

    def __repr__(self):
        return f'<User {self.email}>'

class Product(db.Model):
    __tablename__ = 'products'
    id = db.Column('product_id', db.Integer, primary_key=True)  # Match the foreign key reference
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    price = db.Column(db.Numeric(10, 2), nullable=False)
    image = db.Column(db.String(500))  # Increased from default length to 500
    image_data = db.Column(db.LargeBinary(length=(2**32)-1))  # Using LONGBLOB
    image_mimetype = db.Column(db.String(100))  # For storing image type
    category = db.Column(db.String(50))
    discount = db.Column(db.Integer, default=0)
    stock_quantity = db.Column(db.Integer, default=0)
    reviews = db.relationship('Review', backref='product', lazy=True)

    def get_discounted_price(self):
        if self.discount:
            discount_factor = Decimal('1.0') - (Decimal(str(self.discount)) / Decimal('100.0'))
            return self.price * discount_factor
        return self.price

    def update_stock(self, quantity):
        if self.stock_quantity >= quantity:
            self.stock_quantity -= quantity
            return True
        return False

    def get_image_url(self):
        if self.image_data:
            return url_for('serve_image', product_id=self.id)
        elif self.image:
            return url_for('static', filename=f'images/{self.image}')
        return url_for('static', filename='images/default.jpg')

    def __repr__(self):
        return f'<Product {self.name}>'

class ReviewMedia(db.Model):
    __tablename__ = 'review_media'
    id = db.Column(db.Integer, primary_key=True)
    review_id = db.Column(db.Integer, db.ForeignKey('reviews.id'), nullable=False)
    media_data = db.Column(db.LargeBinary(length=(2**32)-1))
    media_type = db.Column(db.String(20))  # 'image' or 'video'
    media_mimetype = db.Column(db.String(100))

class Review(db.Model):
    __tablename__ = 'reviews'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('products.product_id'), nullable=False)
    rating = db.Column(db.Integer, nullable=False)
    review_text = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    helpful_count = db.Column(db.Integer, default=0)
    # Add image fields
    review_image = db.Column(db.LargeBinary(length=(2**32)-1))  # For storing image data
    image_mimetype = db.Column(db.String(100))  # For storing image type
    media = db.relationship('ReviewMedia', backref='review', lazy=True, cascade='all, delete-orphan')

    def get_image_url(self):
        if self.review_image:
            return url_for('serve_review_image', review_id=self.id)
        return None

    def __repr__(self):
        return f'<Review {self.id}>'

class Order(db.Model):
    __tablename__ = 'orders'  # Match existing table name
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    user = db.relationship('User', backref=db.backref('orders', lazy=True))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(20), nullable=False, default='pending')  # pending, confirmed, shipped, delivered, cancelled
    items = db.relationship('OrderItem', backref='order', lazy=True)
    shipping_address = db.Column(db.Text, nullable=True)
    shipping_city = db.Column(db.String(100), nullable=True)
    shipping_state = db.Column(db.String(100), nullable=True)
    shipping_zip = db.Column(db.String(20), nullable=True)
    tracking_number = db.Column(db.String(100), nullable=True)
    notes = db.Column(db.Text, nullable=True)
    # Add relationship to Payment without backref
    payment = db.relationship('Payment', backref='order_info', lazy=True, uselist=False)

    @property
    def total_amount(self):
        return sum(item.subtotal for item in self.items)

    def get_status_display(self):
        return self.status.title()

class OrderItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('products.product_id'))
    product_name = db.Column(db.String(100), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    price_at_time = db.Column(db.Float, nullable=False)  # Store price at time of purchase
    discount_at_time = db.Column(db.Integer, nullable=True)  # Store discount at time of purchase

    def __init__(self, order_id, product_id, quantity, price_at_time, discount_at_time=0):
        self.order_id = order_id
        self.product_id = product_id
        product = Product.query.get(product_id)
        self.product_name = product.name if product else None
        self.quantity = quantity
        self.price_at_time = price_at_time
        self.discount_at_time = discount_at_time

    @property
    def subtotal(self):
        if self.discount_at_time:
            discounted_price = self.price_at_time * (1 - self.discount_at_time/100)
            return discounted_price * self.quantity
        return self.price_at_time * self.quantity

class Payment(db.Model):
    __tablename__ = 'payments'
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id'), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    payment_date = db.Column(db.DateTime, default=datetime.utcnow)
    payment_status = db.Column(db.String(20), nullable=False)
    payment_method = db.Column(db.String(50), nullable=False)
    transaction_id = db.Column(db.String(100), nullable=True)
    # Add card details columns
    card_number_hash = db.Column(db.String(256), nullable=True)  # Store full number hashed
    card_last_four = db.Column(db.String(4), nullable=True)  # Store last 4 digits for display

    def set_card_number(self, card_number):
        if card_number:
            self.card_number_hash = hash_card_number(card_number)
            self.card_last_four = get_last_four_digits(card_number)

    def get_masked_card_number(self):
        if self.card_last_four:
            return f"****-****-****-{self.card_last_four}"
        return None

class PaymentDetails(db.Model):
    __tablename__ = 'payment_details'
    id = db.Column(db.Integer, primary_key=True)
    payment_id = db.Column(db.Integer, db.ForeignKey('payments.id'), nullable=False)
    card_number = db.Column(db.String(16))  # Store last 4 digits only in production
    card_expiry = db.Column(db.String(5))
    card_holder = db.Column(db.String(100))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Cart(db.Model):
    cart_id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('products.product_id'), nullable=False)
    product_name = db.Column(db.String(100), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    user = db.relationship('User', backref='cart_items', lazy=True)
    product = db.relationship('Product', backref='cart_entries', lazy=True)
    
    def __init__(self, user_id, product_id, quantity):
        self.user_id = user_id
        self.product_id = product_id
        product = Product.query.get(product_id)
        self.product_name = product.name if product else None
        self.quantity = quantity
