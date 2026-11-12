# Android Element Locators Reference

All locators mapped in this test automation framework are extracted directly from the official layout XML definitions and source files of [Sauce Labs My Demo App Android](https://github.com/saucelabs/my-demo-app-android).

Per framework architectural standards:
- **Primary strategy:** Accessibility ID (`content-desc`) or fully qualified Resource ID (`package:id/<view_id>`).
- **Never used:** Positional XPath (`//android.widget.TextView[3]`), coordinates, or volatile absolute paths.

---

## 1. Top Navigation & Header

Source layout: [`app/src/main/res/layout/menu_header_layout.xml`](https://github.com/saucelabs/my-demo-app-android/blob/main/app/src/main/res/layout/menu_header_layout.xml)

| Logical Element | Strategy | Locator Value | Source File / Attribution | Description |
|---|---|---|---|---|
| Menu Button | `AppiumBy.ACCESSIBILITY_ID` | `View menu` | `menu_header_layout.xml` (`@id/menuIV`, `@string/tap_to_view_menu`) | Opens the left navigation drawer |
| Menu Button (ID fallback) | `AppiumBy.ID` | `com.saucelabs.mydemoapp.android:id/menuIV` | `menu_header_layout.xml` (`@id/menuIV`) | Direct resource ID |
| Sort Button | `AppiumBy.ACCESSIBILITY_ID` | `Shows current sorting order and displays available sorting options` | `menu_header_layout.xml` (`@id/sortIV`, `@string/shows_current_sorting_order_and_displays_available_sorting_options`) | Opens sorting dialog modal |
| Sort Button (ID fallback) | `AppiumBy.ID` | `com.saucelabs.mydemoapp.android:id/sortIV` | `menu_header_layout.xml` (`@id/sortIV`) | Direct resource ID |
| Cart Icon Container | `AppiumBy.ACCESSIBILITY_ID` | `View cart` | `menu_header_layout.xml` (`@id/cartRL`, `@string/tap_to_view_you_cart`) | Opens the Cart screen |
| Cart Icon (ID fallback) | `AppiumBy.ID` | `com.saucelabs.mydemoapp.android:id/cartRL` | `menu_header_layout.xml` (`@id/cartRL`) | Clickable cart relative layout |
| Cart Item Badge Counter | `AppiumBy.ID` | `com.saucelabs.mydemoapp.android:id/cartTV` | `menu_header_layout.xml` (`@id/cartTV`) | Displays the numerical badge of items in cart |

---

## 2. Navigation Drawer Menu

Source layout: [`app/src/main/res/layout/navigation_layout.xml`](https://github.com/saucelabs/my-demo-app-android/blob/main/app/src/main/res/layout/navigation_layout.xml), [`app/src/main/res/layout/menu_item.xml`](https://github.com/saucelabs/my-demo-app-android/blob/main/app/src/main/res/layout/menu_item.xml), and [`MainActivity.java`](https://github.com/saucelabs/my-demo-app-android/blob/main/app/src/main/java/com/saucelabs/mydemoapp/android/view/activities/MainActivity.java)

| Logical Element | Strategy | Locator Value | Source File / Attribution | Description |
|---|---|---|---|---|
| Menu RecyclerView | `AppiumBy.ID` | `com.saucelabs.mydemoapp.android:id/menuRV` | `navigation_layout.xml` (`@id/menuRV`) | Container of navigation menu options |
| Menu Item Text | `AppiumBy.ID` | `com.saucelabs.mydemoapp.android:id/itemTV` | `menu_item.xml` (`@id/itemTV`) | Individual menu entry label |
| Login Menu Item | `AppiumBy.ACCESSIBILITY_ID` | `Login Menu Item` | `MainActivity.java` (`setMenu()` content description) | Drawer option to navigate to login |
| Logout Menu Item | `AppiumBy.ACCESSIBILITY_ID` | `Logout Menu Item` | `MainActivity.java` (`setMenu()` content description) | Drawer option displayed when logged in |

---

## 3. Product Catalog Screen

Source layout: [`app/src/main/res/layout/fragment_product_catalog.xml`](https://github.com/saucelabs/my-demo-app-android/blob/main/app/src/main/res/layout/fragment_product_catalog.xml) and [`app/src/main/res/layout/item_products.xml`](https://github.com/saucelabs/my-demo-app-android/blob/main/app/src/main/res/layout/item_products.xml)

| Logical Element | Strategy | Locator Value | Source File / Attribution | Description |
|---|---|---|---|---|
| Catalog Title | `AppiumBy.ID` | `com.saucelabs.mydemoapp.android:id/productTV` | `fragment_product_catalog.xml` (`@id/productTV`) | Header text ("Products") |
| Catalog RecyclerView | `AppiumBy.ID` | `com.saucelabs.mydemoapp.android:id/productRV` | `fragment_product_catalog.xml` (`@id/productRV`) | Product grid container |
| Product Item Card / Image | `AppiumBy.ID` | `com.saucelabs.mydemoapp.android:id/productIV` | `item_products.xml` (`@id/productIV`, `ProductsAdapter.java`) | Clickable product image opening details |
| Product Item Title | `AppiumBy.ID` | `com.saucelabs.mydemoapp.android:id/titleTV` | `item_products.xml` (`@id/titleTV`) | Product name label |
| Product Item Price | `AppiumBy.ID` | `com.saucelabs.mydemoapp.android:id/priceTV` | `item_products.xml` (`@id/priceTV`) | Product price label (e.g. "$ 29.99") |

---

## 4. Sorting Dialog Modal

Source layout: [`app/src/main/res/layout/sort_dialog.xml`](https://github.com/saucelabs/my-demo-app-android/blob/main/app/src/main/res/layout/sort_dialog.xml)

| Logical Element | Strategy | Locator Value | Source File / Attribution | Description |
|---|---|---|---|---|
| Sort by Price Ascending | `AppiumBy.ACCESSIBILITY_ID` | `Ascending order by price` | `sort_dialog.xml` (`@id/priceAscCL`, `@string/ascending_order_by_price`) | Sort products: lowest price first |
| Sort by Price Ascending (ID) | `AppiumBy.ID` | `com.saucelabs.mydemoapp.android:id/priceAscCL` | `sort_dialog.xml` (`@id/priceAscCL`) | Layout container for price ascending |
| Sort by Price Descending | `AppiumBy.ACCESSIBILITY_ID` | `Descending order by price` | `sort_dialog.xml` (`@id/priceDesCL`, `@string/descending_order_by_price`) | Sort products: highest price first |
| Sort by Price Descending (ID) | `AppiumBy.ID` | `com.saucelabs.mydemoapp.android:id/priceDesCL` | `sort_dialog.xml` (`@id/priceDesCL`) | Layout container for price descending |
| Sort by Name Ascending | `AppiumBy.ACCESSIBILITY_ID` | `Ascending order by name` | `sort_dialog.xml` (`@id/nameAscCL`, `@string/ascending_order_by_name`) | Sort products: A to Z |
| Sort by Name Descending | `AppiumBy.ACCESSIBILITY_ID` | `Descending order by name` | `sort_dialog.xml` (`@id/nameDesCL`, `@string/descending_order_by_name`) | Sort products: Z to A |

---

## 5. Product Detail Screen

Source layout: [`app/src/main/res/layout/fragment_product_detail.xml`](https://github.com/saucelabs/my-demo-app-android/blob/main/app/src/main/res/layout/fragment_product_detail.xml)

| Logical Element | Strategy | Locator Value | Source File / Attribution | Description |
|---|---|---|---|---|
| Detail Product Title | `AppiumBy.ID` | `com.saucelabs.mydemoapp.android:id/productTV` | `fragment_product_detail.xml` (`@id/productTV`) | Header displaying product title |
| Detail Product Price | `AppiumBy.ID` | `com.saucelabs.mydemoapp.android:id/priceTV` | `fragment_product_detail.xml` (`@id/priceTV`) | Displayed product price |
| Quantity Value | `AppiumBy.ID` | `com.saucelabs.mydemoapp.android:id/noTV` | `fragment_product_detail.xml` (`@id/noTV`) | Current quantity to add |
| Increase Quantity Button | `AppiumBy.ACCESSIBILITY_ID` | `Increase item quantity` | `fragment_product_detail.xml` (`@id/plusIV`, `@string/increase_item_quantity`) | Increments item quantity |
| Increase Quantity (ID) | `AppiumBy.ID` | `com.saucelabs.mydemoapp.android:id/plusIV` | `fragment_product_detail.xml` (`@id/plusIV`) | Plus image button |
| Decrease Quantity Button | `AppiumBy.ACCESSIBILITY_ID` | `Decrease item quantity` | `fragment_product_detail.xml` (`@id/minusIV`, `@string/decrease_item_quantity`) | Decrements item quantity |
| Add to Cart Button | `AppiumBy.ACCESSIBILITY_ID` | `Tap to add product to cart` | `fragment_product_detail.xml` (`@id/cartBt`, `@string/tap_to_add_product_to_cart`) | Submits item to cart |
| Add to Cart (ID fallback) | `AppiumBy.ID` | `com.saucelabs.mydemoapp.android:id/cartBt` | `fragment_product_detail.xml` (`@id/cartBt`) | Primary action button |

---

## 6. Cart Screen

Source layout: [`app/src/main/res/layout/fragment_cart.xml`](https://github.com/saucelabs/my-demo-app-android/blob/main/app/src/main/res/layout/fragment_cart.xml) and [`app/src/main/res/layout/item_my_cart.xml`](https://github.com/saucelabs/my-demo-app-android/blob/main/app/src/main/res/layout/item_my_cart.xml)

| Logical Element | Strategy | Locator Value | Source File / Attribution | Description |
|---|---|---|---|---|
| Cart Items RecyclerView | `AppiumBy.ID` | `com.saucelabs.mydemoapp.android:id/productRV` | `fragment_cart.xml` (`@id/productRV`) | List of items currently in cart |
| Cart Total Items Label | `AppiumBy.ID` | `com.saucelabs.mydemoapp.android:id/itemsTV` | `fragment_cart.xml` (`@id/itemsTV`) | Item count summary (e.g. "1 items") |
| Cart Total Price Label | `AppiumBy.ID` | `com.saucelabs.mydemoapp.android:id/totalPriceTV` | `fragment_cart.xml` (`@id/totalPriceTV`) | Cart subtotal amount |
| Remove Item Button | `AppiumBy.ACCESSIBILITY_ID` | `Removes product from cart` | `item_my_cart.xml` (`@id/removeBt`, `@string/removes_product_from_cart`) | Removes row from shopping cart |
| Remove Item Button (ID) | `AppiumBy.ID` | `com.saucelabs.mydemoapp.android:id/removeBt` | `item_my_cart.xml` (`@id/removeBt`) | Direct text button resource ID |
| Empty Cart Header | `AppiumBy.ID` | `com.saucelabs.mydemoapp.android:id/noItemTitleTV` | `fragment_cart.xml` (`@id/noItemTitleTV`) | Displays "No Items" when cart is empty |
| Go Shopping Button | `AppiumBy.ID` | `com.saucelabs.mydemoapp.android:id/shoppingBt` | `fragment_cart.xml` (`@id/shoppingBt`) | Navigation button back to catalog |

---

## 7. Login Screen

Source layout: [`app/src/main/res/layout/fragment_login.xml`](https://github.com/saucelabs/my-demo-app-android/blob/main/app/src/main/res/layout/fragment_login.xml) and [`LoginFragment.java`](https://github.com/saucelabs/my-demo-app-android/blob/main/app/src/main/java/com/saucelabs/mydemoapp/android/view/fragments/LoginFragment.java)

| Logical Element | Strategy | Locator Value | Source File / Attribution | Description |
|---|---|---|---|---|
| Login Title | `AppiumBy.ID` | `com.saucelabs.mydemoapp.android:id/loginTV` | `fragment_login.xml` (`@id/loginTV`) | Screen header ("Login") |
| Username Field | `AppiumBy.ID` | `com.saucelabs.mydemoapp.android:id/nameET` | `fragment_login.xml` (`@id/nameET`) | Text input for user email |
| Password Field | `AppiumBy.ID` | `com.saucelabs.mydemoapp.android:id/passwordET` | `fragment_login.xml` (`@id/passwordET`) | Text input for password |
| Login Button | `AppiumBy.ACCESSIBILITY_ID` | `Tap to login with given credentials` | `fragment_login.xml` (`@id/loginBtn`, `@string/tap_to_login_with_given_credentials`) | Submit authentication form |
| Login Button (ID fallback) | `AppiumBy.ID` | `com.saucelabs.mydemoapp.android:id/loginBtn` | `fragment_login.xml` (`@id/loginBtn`) | Resource ID for button |
| Demo User: Standard User | `AppiumBy.ID` | `com.saucelabs.mydemoapp.android:id/username1TV` | `fragment_login.xml` (`@id/username1TV`) | Tap to autofill `bod@example.com` |
| Demo User: Locked-out User | `AppiumBy.ID` | `com.saucelabs.mydemoapp.android:id/username2TV` | `fragment_login.xml` (`@id/username2TV`) | Tap to autofill `alice@example.com (locked out)` |
| Password / Locked Out Error | `AppiumBy.ID` | `com.saucelabs.mydemoapp.android:id/passwordErrorTV` | `fragment_login.xml` (`@id/passwordErrorTV`), `LoginFragment.java` | Text view displaying `"Sorry this user has been locked out."` |
| Username Error Label | `AppiumBy.ID` | `com.saucelabs.mydemoapp.android:id/nameErrorTV` | `fragment_login.xml` (`@id/nameErrorTV`) | Displays validation error when username is empty |
