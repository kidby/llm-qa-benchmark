# Requirement: Shopping cart quantity & checkout

A shopping cart holds line items, each with a product and a quantity.

- Quantity per line item is an integer from 1 to 99.
- Setting a quantity to 0 removes the line item.
- Each product has a stock level; the cart cannot exceed available stock.
- A promo code "SAVE10" gives 10% off the subtotal, applied once; invalid or
  expired codes are rejected with a message and no discount.
- Free shipping applies when the subtotal (after discount) is at least $50.
- Checkout is blocked if any line item exceeds stock or the cart is empty.
