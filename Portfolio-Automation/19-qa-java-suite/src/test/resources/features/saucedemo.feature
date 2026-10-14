Feature: SauceDemo user journeys
  As a user
  I want to use the SauceDemo site
  So that I can purchase items and observe known behaviors

  @known-bug
  Scenario: Some add to cart buttons are broken
    Given I am logged in as "problem_user" with password "secret_sauce"
    When I add all six products to the cart
    Then the cart badge should not show "6"

  @known-bug
  Scenario: Last name cannot be filled in checkout
    Given I am logged in as "problem_user" with password "secret_sauce"
    When I add the backpack to the cart
    And I go to checkout and fill form with "John", "Doe", "12345"
    Then I should see the error "Last Name is required"

  @known-bug
  Scenario: Remove button on the inventory page does nothing
    Given I am logged in as "problem_user" with password "secret_sauce"
    When I add the backpack to the cart
    And I remove the backpack from the inventory page
    Then the cart badge should show "1"

  Scenario: Add multiple products to cart
    Given I am logged in as "standard_user" with password "secret_sauce"
    When I add the backpack to the cart
    And I add the bike light to the cart
    Then the cart badge should show "2"

  Scenario: Complete checkout journey successfully
    Given I am logged in as "standard_user" with password "secret_sauce"
    When I add the backpack to the cart
    And I add the bike light to the cart
    And I complete the checkout with "Jane", "Doe", "90210"
    Then I should see the complete order confirmation "Thank you for your order!"

  Scenario: Checkout with empty first name shows validation error
    Given I am logged in as "standard_user" with password "secret_sauce"
    When I add the backpack to the cart
    And I go to checkout and fill form with "", "Doe", "90210"
    Then I should see the exact error "Error: First Name is required"

  Scenario: Checkout with empty postal code shows validation error
    Given I am logged in as "standard_user" with password "secret_sauce"
    When I add the backpack to the cart
    And I go to checkout and fill form with "Jane", "Doe", ""
    Then I should see the exact error "Error: Postal Code is required"
