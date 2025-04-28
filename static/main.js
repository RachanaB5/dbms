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
        // Use the correct static path for images
        productCard.innerHTML = `
            <div class="product-image" style="background-image: url('/static/image/${product.image}')"></div>
            <h3 class="product-title">${product.name}</h3>
            <div class="product-rating">${'⭐'.repeat(product.rating)} (${product.reviews})</div>
            <div class="product-price">₹${product.price.toLocaleString()}</div>
            <button class="add-to-cart" data-id="${product.id}">Add to Cart</button>
        `;
        container.appendChild(productCard);
    });
}

// Cart logic (in-memory, with quantity)
let cart = [];

// Persist cart in localStorage
function saveCart() {
    localStorage.setItem('cart', JSON.stringify(cart));
}

function loadCart() {
    const saved = localStorage.getItem('cart');
    if (saved) cart = JSON.parse(saved);
}

function addToCart(productId) {
    const product = products.find(p => p.id === productId);
    if (product) {
        const cartItem = cart.find(item => item.id === productId);
        if (cartItem) {
            cartItem.quantity += 1;
        } else {
            cart.push({ ...product, quantity: 1 });
        }
        updateCartCount();
        updateCartDropdown();
        saveCart();
        alert(`${product.name} added to cart!`);
    }
}

function updateCartCount() {
    const count = cart.reduce((sum, item) => sum + item.quantity, 0);
    const cartCountElem = document.querySelector('.cart-count');
    if (cartCountElem) cartCountElem.textContent = count;
}

function updateCartDropdown() {
    const cartDropdown = document.getElementById('cartDropdown');
    const cartItemsContainer = document.getElementById('cartItemsContainer');
    const cartTotalSection = document.getElementById('cartTotalSection');
    const emptyCartMessage = document.getElementById('emptyCartMessage');
    const cartItemCount = document.getElementById('cartItemCount');
    const cartTotalAmount = document.getElementById('cartTotalAmount');
    if (!cartItemsContainer || !cartTotalSection || !emptyCartMessage || !cartItemCount || !cartTotalAmount) return;

    if (cart.length === 0) {
        cartItemsContainer.innerHTML = '';
        cartItemsContainer.style.display = 'none';
        cartTotalSection.style.display = 'none';
        emptyCartMessage.style.display = 'block';
        cartItemCount.textContent = '0';
        cartTotalAmount.textContent = '₹0.00';
        return;
    }

    emptyCartMessage.style.display = 'none';
    cartTotalSection.style.display = 'block';
    cartItemsContainer.style.display = 'block'; // Ensure cart items are visible
    cartItemsContainer.innerHTML = '';
    let total = 0;
    let itemCount = 0;
    cart.forEach(item => {
        total += item.price * item.quantity;
        itemCount += item.quantity;
        const div = document.createElement('div');
        div.className = 'cart-item';
        div.innerHTML = `
            <span>${item.name}</span>
            <span>Qty: ${item.quantity}</span>
            <span>₹${(item.price * item.quantity).toLocaleString()}</span>
            <button class="remove-item" data-id="${item.id}">Remove</button>
        `;
        cartItemsContainer.appendChild(div);
    });
    cartItemCount.textContent = itemCount;
    cartTotalAmount.textContent = `₹${total.toLocaleString()}`;
    saveCart();
}

// Close login modal when sign in is successful
function closeLoginModal() {
    const loginModal = document.getElementById('loginModal');
    if (loginModal) loginModal.style.display = 'none';
}

// Attach event listener to login form for closing modal on sign in
function setupLoginModalClose() {
    const loginForm = document.getElementById('loginForm');
    if (loginForm) {
        loginForm.addEventListener('submit', function(e) {
            e.preventDefault();
            // ...existing sign in logic...
            closeLoginModal();
        });
    }
}

// Handle login form submission
function handleLogin() {
    const loginForm = document.getElementById('loginForm');
    if (loginForm) {
        loginForm.addEventListener('submit', function(e) {
            e.preventDefault();
            const email = document.getElementById('loginEmail')?.value || '';
            const password = document.getElementById('loginPassword')?.value || '';
            if (email && password) {
                // Simulate login success
                localStorage.setItem('isLoggedIn', 'true');
                localStorage.setItem('username', email.split('@')[0]);
                const greeting = document.getElementById('greeting');
                if (greeting) greeting.textContent = `Hello, ${email.split('@')[0]}`;
                closeLoginModal();
                alert('Login successful!');
            } else {
                alert('Please enter both email and password');
            }
        });
    }
}

// Show greeting if user is already logged in
function showGreetingIfLoggedIn() {
    if (localStorage.getItem('isLoggedIn') === 'true') {
        const username = localStorage.getItem('username') || 'sign in';
        const greeting = document.getElementById('greeting');
        if (greeting) greeting.textContent = `Hello, ${username}`;
    }
}

// Language Selector Interactivity and Persistence
function setLanguage(lang, flag) {
    localStorage.setItem('selectedLang', lang);
    localStorage.setItem('selectedFlag', flag);
    const flagElem = document.querySelector('.flag');
    const languageSelect = document.getElementById('languageSelect');
    if (flagElem) flagElem.textContent = flag;
    if (languageSelect) languageSelect.value = lang;
}

// Event listeners
function setupEventListeners() {
    document.addEventListener('click', function(e) {
        if (e.target.classList.contains('add-to-cart')) {
            const productId = parseInt(e.target.getAttribute('data-id'));
            addToCart(productId);
        }
        if (e.target.classList.contains('remove-item')) {
            const productId = parseInt(e.target.getAttribute('data-id'));
            cart = cart.filter(item => item.id !== productId);
            updateCartCount();
            updateCartDropdown();
            saveCart();
        }
    });
}

document.addEventListener('DOMContentLoaded', function() {
    loadCart();
    renderProducts();
    setupEventListeners();
    updateCartCount();
    updateCartDropdown();
    setupLoginModalClose();
    handleLogin();
    showGreetingIfLoggedIn();

    // Helper to show login modal from any trigger
    function showLoginModal(e) {
        if (e) e.preventDefault();
        const loginModal = document.getElementById('loginModal');
        if (loginModal) loginModal.style.display = 'block';
    }
    // Attach to all sign in triggers
    const signInButton = document.getElementById('signInButton');
    if (signInButton) signInButton.onclick = showLoginModal;
    const mainSignInButton = document.getElementById('mainSignInButton');
    if (mainSignInButton) mainSignInButton.onclick = showLoginModal;
    const heroLoginLink = document.getElementById('heroLoginLink');
    if (heroLoginLink) heroLoginLink.onclick = showLoginModal;

    // Optional: Close modal when clicking outside of it
    const loginModal = document.getElementById('loginModal');
    window.addEventListener('click', function(event) {
        if (event.target === loginModal) {
            loginModal.style.display = 'none';
        }
    });

    // Logout functionality
    const signOutLink = document.getElementById('signOutLink');
    if (signOutLink) {
        signOutLink.addEventListener('click', function(e) {
            e.preventDefault();
            localStorage.removeItem('isLoggedIn');
            localStorage.removeItem('username');
            const greeting = document.getElementById('greeting');
            if (greeting) greeting.textContent = 'Hello, sign in';
            alert('You have been logged out.');
            // Optionally, reload the page to update UI
            window.location.reload();
        });
    }

    // --- Navbar Interactivity ---

    // Location Dropdown
    const locationDropdown = document.getElementById('locationDropdown');
    const locationContent = locationDropdown?.querySelector('.location-dropdown-content');
    const selectedLocation = document.getElementById('selectedLocation');
    if (locationDropdown && locationContent) {
        locationDropdown.addEventListener('click', function(e) {
            e.stopPropagation();
            locationContent.style.display = locationContent.style.display === 'block' ? 'none' : 'block';
        });
        document.querySelectorAll('.location-item').forEach(item => {
            item.addEventListener('click', function() {
                if (selectedLocation) selectedLocation.textContent = this.getAttribute('data-location');
                locationContent.style.display = 'none';
            });
        });
        document.addEventListener('click', function() {
            locationContent.style.display = 'none';
        });
    }

    // Language Selector
    const languageDropdown = document.getElementById('languageDropdown');
    const languageContent = languageDropdown?.querySelector('.language-dropdown-content');
    const flagElem = languageDropdown?.querySelector('.flag');
    const languageSelect = document.getElementById('languageSelect');
    // Restore language from localStorage
    const savedLang = localStorage.getItem('selectedLang');
    const savedFlag = localStorage.getItem('selectedFlag');
    if (savedLang && savedFlag) {
        setLanguage(savedLang, savedFlag);
    }
    if (languageDropdown && languageContent) {
        languageDropdown.addEventListener('click', function(e) {
            e.stopPropagation();
            languageContent.style.display = languageContent.style.display === 'block' ? 'none' : 'block';
        });
        document.querySelectorAll('.language-item').forEach(item => {
            item.addEventListener('click', function() {
                const lang = this.getAttribute('data-lang');
                const flag = this.getAttribute('data-flag');
                setLanguage(lang, flag);
                languageContent.style.display = 'none';
            });
        });
        document.addEventListener('click', function() {
            languageContent.style.display = 'none';
        });
    }

    // Account Dropdown
    const accountDropdown = document.getElementById('accountDropdown');
    const accountContent = accountDropdown?.querySelector('.account-dropdown-content');
    if (accountDropdown && accountContent) {
        accountDropdown.addEventListener('click', function(e) {
            e.stopPropagation();
            accountContent.style.display = accountContent.style.display === 'block' ? 'none' : 'block';
        });
        document.addEventListener('click', function() {
            accountContent.style.display = 'none';
        });
    }

    // Cart Dropdown
    const cartButton = document.getElementById('cartButton');
    const cartDropdown = document.getElementById('cartDropdown');
    if (cartButton && cartDropdown) {
        cartButton.addEventListener('click', function(e) {
            e.stopPropagation();
            cartDropdown.style.display = cartDropdown.style.display === 'block' ? 'none' : 'block';
        });
        document.addEventListener('click', function() {
            cartDropdown.style.display = 'none';
        });
    }

    // Hamburger Menu (if present)
    const mainMenuDropdown = document.getElementById('mainMenuDropdown');
    const menuContent = mainMenuDropdown?.querySelector('.menu-dropdown-content');
    if (mainMenuDropdown && menuContent) {
        mainMenuDropdown.addEventListener('click', function(e) {
            e.stopPropagation();
            menuContent.style.display = menuContent.style.display === 'flex' ? 'none' : 'flex';
        });
        document.addEventListener('click', function() {
            menuContent.style.display = 'none';
        });
    }

    // Highlight active nav item (basic example for links)
    const navLinks = document.querySelectorAll('.panelops a');
    navLinks.forEach(link => {
        if (window.location.pathname.includes(link.getAttribute('href'))) {
            link.classList.add('active');
        }
    });
});
