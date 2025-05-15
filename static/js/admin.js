function editProduct(productId) {
    fetch(`/admin/product/${productId}`)
        .then(response => response.json())
        .then(product => {
            // Populate edit modal with product data
            document.getElementById('editProductId').value = product.id;
            document.getElementById('editProductName').value = product.name;
            document.getElementById('editProductDescription').value = product.description;
            document.getElementById('editProductPrice').value = product.price;
            document.getElementById('editProductCategory').value = product.category;
            document.getElementById('editProductStock').value = product.stock_quantity;
            $('#editProductModal').modal('show');
        });
}

function deleteProduct(productId) {
    if (confirm('Are you sure you want to delete this product?')) {
        fetch(`/admin/product/delete/${productId}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        }).then(() => {
            location.reload();
        });
    }
}

function updateOrderStatus(orderId, status) {
    fetch(`/admin/order/${orderId}/status`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({ status: status })
    }).then(() => {
        location.reload();
    });
}
