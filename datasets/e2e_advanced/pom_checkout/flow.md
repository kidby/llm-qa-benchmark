# Scenario: Browse from sign-in to an item's detail

The app spans several pages. A test should walk the full journey and stay readable
and maintainable as the journey grows across those pages.

1. From the home page, sign in with username `demo` and password `password123`.
2. The dashboard lists items. Open the item titled "USB-C Hub".
3. The item's detail page shows its title and price.

Keep the page interactions organized so the test would be easy to extend if more
pages were added to the journey.
