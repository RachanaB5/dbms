script.js
// All cart logic is now handled in main.js. This file is reserved for extra UI features only.
// If you need to add custom UI scripts, do so below:

// Example: Highlight navbar on scroll
// window.addEventListener('scroll', function() {
//     document.querySelector('.navbar').classList.toggle('scrolled', window.scrollY > 0);
// });

document.addEventListener('DOMContentLoaded', function() {
    // Handle cart modal
    const cartModal = document.getElementById('cartModal');
    const cartButton = document.getElementById('cartButton');
    const closeModalButton = document.querySelector('.close-modal');
    const continueShoppingButtons = document.querySelectorAll('.continue-shopping');

    if (cartButton) {
        cartButton.addEventListener('click', function(e) {
            e.preventDefault();
            e.stopPropagation();
            updateCartContents();
        });
    }

    if (closeModalButton) {
        closeModalButton.addEventListener('click', () => {
            cartModal.style.display = 'none';
        });
    }

    continueShoppingButtons.forEach(button => {
        button.addEventListener('click', () => {
            cartModal.style.display = 'none';
        });
    });

    // Close modal when clicking outside
    window.addEventListener('click', (event) => {
        if (event.target === cartModal) {
            cartModal.style.display = 'none';
        }
    });

    // Add to cart form submission
    const addToCartForms = document.querySelectorAll('.add-to-cart-form');
    addToCartForms.forEach(form => {
        form.addEventListener('submit', function(e) {
            e.preventDefault();
            const formData = new FormData(this);
            
            fetch(this.action, {
                method: 'POST',
                body: formData,
                headers: {
                    'X-Requested-With': 'XMLHttpRequest'
                }
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    updateCartContents();
                } else {
                    alert(data.error || 'Failed to add item to cart');
                }
            })
            .catch(error => {
                console.error('Error:', error);
                alert('Failed to add item to cart');
            });
        });
    });

    // Update cart quantity
    function updateCartContents() {
        fetch('/cart', {
            headers: {
                'X-Requested-With': 'XMLHttpRequest'
            }
        })
        .then(response => response.json())
        .then(data => {
            if (data.error) {
                console.error('Error:', data.error);
                return;
            }

            const cartItemsContainer = document.querySelector('.cart-items-container');
            const cartSummary = document.querySelector('.cart-summary');
            const emptyCartMessage = document.querySelector('.empty-cart-message');
            const cartBadge = document.querySelector('.fab-badge');
            const cartTotal = document.getElementById('cartTotal');
            
            // Update cart count badge
            if (cartBadge) {
                cartBadge.textContent = data.count;
            }

            // Show cart modal
            if (cartModal) {
                cartModal.style.display = 'block';
            }

            if (data.items && data.items.length > 0) {
                cartItemsContainer.innerHTML = data.items.map(item => `
                    <div class="cart-item">
                        <img src="${item.image}" alt="${item.name}" class="cart-item-image">
                        <div class="cart-item-details">
                            <h3 class="cart-item-title">${item.name}</h3>
                            <div class="cart-item-price">
                                ${item.discount ? 
                                    `<span class="original-price">₹${item.original_price.toFixed(2)}</span>
                                    <span class="discounted-price">₹${item.price.toFixed(2)}</span>` :
                                    `<span class="price">₹${item.price.toFixed(2)}</span>`
                                }
                            </div>
                            <div class="cart-item-controls">
                                <div class="quantity-controls">
                                    <button type="button" class="quantity-btn" data-action="decrease" data-id="${item.id}">-</button>
                                    <span>${item.quantity}</span>
                                    <button type="button" class="quantity-btn" data-action="increase" data-id="${item.id}" ${item.quantity >= item.stock_quantity ? 'disabled' : ''}>+</button>
                                </div>
                                <button type="button" class="remove-item" data-id="${item.id}">Remove</button>
                            </div>
                            <div class="cart-item-subtotal">
                                Subtotal: ₹${item.subtotal.toFixed(2)}
                            </div>
                        </div>
                    </div>
                `).join('');

                if (cartTotal) {
                    cartTotal.textContent = data.total.toFixed(2);
                }
                
                if (cartSummary) {
                    cartSummary.style.display = 'block';
                }
                if (emptyCartMessage) {
                    emptyCartMessage.style.display = 'none';
                }

                // Add event listeners for quantity controls
                document.querySelectorAll('.quantity-btn').forEach(btn => {
                    btn.addEventListener('click', handleQuantityUpdate);
                });

                document.querySelectorAll('.remove-item').forEach(btn => {
                    btn.addEventListener('click', handleRemoveItem);
                });
            } else {
                cartItemsContainer.innerHTML = '';
                if (cartSummary) {
                    cartSummary.style.display = 'none';
                }
                if (emptyCartMessage) {
                    emptyCartMessage.style.display = 'block';
                }
            }
        })
        .catch(error => {
            console.error('Error:', error);
        });
    }

    function handleQuantityUpdate(e) {
        const btn = e.currentTarget;
        const productId = btn.dataset.id;
        const action = btn.dataset.action;

        fetch(`/update_cart/${productId}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/x-www-form-urlencoded',
                'X-Requested-With': 'XMLHttpRequest'
            },
            body: `action=${action}`
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                updateCartContents();
            } else {
                alert(data.error || 'Failed to update cart');
            }
        })
        .catch(error => {
            console.error('Error:', error);
            alert('Failed to update cart');
        });
    }

    function handleRemoveItem(e) {
        const btn = e.currentTarget;
        const productId = btn.dataset.id;

        fetch(`/update_cart/${productId}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/x-www-form-urlencoded',
                'X-Requested-With': 'XMLHttpRequest'
            },
            body: 'action=remove'
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                updateCartContents();
            } else {
                alert(data.error || 'Failed to remove item');
            }
        })
        .catch(error => {
            console.error('Error:', error);
            alert('Failed to remove item');
        });
    }
});