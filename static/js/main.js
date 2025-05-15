// Product data using only available images
const products = [
    {
        id: 1,
        name: "Laptop",
        price: 59999,
        rating: 4,
        reviews: 512,
        image: "image/laptop.jpg"
    },
    {
        id: 2,
        name: "Smart Watch",
        price: 2999,
        rating: 5,
        reviews: 162,
        image: "image/smart-watch.jpg"
    },
    {
        id: 3,
        name: "Tablet",
        price: 39999,
        rating: 5,
        reviews: 994,
        image: "image/tablet.jpg"
    },
    {
        id: 4,
        name: "Gaming Console",
        price: 79999,
        rating: 3,
        reviews: 894,
        image: "image/gaming-console.jpg"
    },
    {
        id: 5,
        name: "Wireless Mouse",
        price: 1999,
        rating: 4,
        reviews: 32,
        image: "image/mouse.jpg"
    },
    {
        id: 6,
        name: "Smart Phone",
        price: 24999,
        rating: 3,
        reviews: 687,
        image: "image/smart-phone.jpg"
    },
    {
        id: 7,
        name: "Keyboard",
        price: 5999,
        rating: 4,
        reviews: 320,
        image: "image/keyboard.jpg"
    },
    {
        id: 8,
        name: "Wireless Bluetooth Headphones",
        price: 1499,
        rating: 4,
        reviews: 125,
        image: "image/headphones.jpg"
    }
];

// Render products to a container with id 'featuredProducts'
function renderProducts() {
    const container = document.getElementById('featuredProducts');
    if (!container) return;
    container.innerHTML = '';
    products.forEach(product => {
        const productCard = document.createElement('div');
        productCard.className = 'product-card';
        productCard.innerHTML = `
            <div class="product-image" style="background-image: url('/static/image/${product.image}')"></div>
            <h3 class="product-title">${product.name}</h3>
            <div class="product-rating">${'⭐'.repeat(product.rating)} (${product.reviews})</div>
            <div class="product-price">₹${product.price.toLocaleString()}</div>
            <form method="POST" action="/add_to_cart/${product.id}">
                <input type="hidden" name="quantity" value="1">
                <button type="submit" class="add-to-cart-btn">Add to Cart</button>
            </form>
        `;
        container.appendChild(productCard);
    });
}

// Initialize the page
document.addEventListener('DOMContentLoaded', function() {
    renderProducts();
});
