from extensions import db
from datetime import datetime
from flask_login import UserMixin

class User(UserMixin, db.Model):
    __tablename__ = 'users'  # Match existing table name
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)  # Changed from 'name'
    email = db.Column(db.String(100), unique=True, nullable=False)
    phone = db.Column(db.String(15), nullable=True)
    password_hash = db.Column(db.String(256), nullable=False)
    _is_admin = db.Column('is_admin', db.Boolean, default=False)
    reviews = db.relationship('Review', backref='user', lazy=True)
    orders = db.relationship('Order', backref='user', lazy=True)

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
    discount = db.Column(db.Integer, nullable=True, default=0)
    stock_quantity = db.Column(db.Integer, nullable=False, default=0)
    reviews = db.relationship('Review', backref='product', lazy=True)
    order_items = db.relationship('OrderItem', backref='product', lazy=True)

    def get_discounted_price(self):
        if self.discount:
            return self.price * (1 - self.discount/100)
        return self.price

    def update_stock(self, quantity):
        if self.stock_quantity >= quantity:
            self.stock_quantity -= quantity
            return True
        return False

class Review(db.Model):
    __tablename__ = 'reviews'  # Match existing table name
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('products.product_id'), nullable=False)
    rating = db.Column(db.Integer, nullable=False)
    review_text = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    helpful_count = db.Column(db.Integer, default=0)

class Order(db.Model):
    __tablename__ = 'orders'  # Match existing table name
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(20), nullable=False, default='pending')  # pending, confirmed, shipped, delivered, cancelled
    items = db.relationship('OrderItem', backref='order', lazy=True)
    shipping_address = db.Column(db.Text, nullable=True)
    shipping_city = db.Column(db.String(100), nullable=True)
    shipping_state = db.Column(db.String(100), nullable=True)
    shipping_zip = db.Column(db.String(20), nullable=True)
    tracking_number = db.Column(db.String(100), nullable=True)
    notes = db.Column(db.Text, nullable=True)

    @property
    def total_amount(self):
        return sum(item.subtotal for item in self.items)

    def get_status_display(self):
        return self.status.title()

class OrderItem(db.Model):
    __tablename__ = 'order_item'  # Match existing table name
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('products.product_id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    price_at_time = db.Column(db.Float, nullable=False)  # Store price at time of purchase
    discount_at_time = db.Column(db.Integer, nullable=True)  # Store discount at time of purchase

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
    payment_status = db.Column(db.String(20), nullable=False)  # pending, completed, failed, refunded
    payment_method = db.Column(db.String(50), nullable=False)  # credit_card, debit_card, upi, net_banking
    transaction_id = db.Column(db.String(100), nullable=True)
    order = db.relationship('Order', backref='payment', lazy=True, uselist=False)

class Cart(db.Model):
    __tablename__ = 'cart'
    id = db.Column('cart_id', db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('products.product_id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False, default=1)
    user = db.relationship('User', backref='cart_items', lazy=True)
    product = db.relationship('Product', backref='cart_entries', lazy=True)
