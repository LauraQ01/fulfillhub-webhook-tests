Feature: Out-of-Order Event Handling
  As the FulfillHub payment system
  I want to handle webhooks that arrive out of chronological order
  So that the payment state machine never crashes

  Scenario Outline: Out-of-order events do not cause server errors
    Given a payment "pay_001" exists in "pending" status
    When I send a "<out_of_order_event>" webhook before its prerequisite event
    Then the response status should not be a 5xx error

    Examples:
      | out_of_order_event  |
      | payment.declined    |
      | payment.captured    |

  Scenario: Out-of-order delivery eventually reaches correct final state
    Given a payment "pay_001" exists in "pending" status
    When I send a "payment.captured" webhook for payment "pay_001"
    And I send a "payment.authorized" webhook for payment "pay_001"
    Then the payment "pay_001" status should be "captured"
    And all 2 events should be stored in the database

  Scenario: Full payment lifecycle delivered in reverse order reaches settled
    Given a payment "pay_001" exists in "pending" status
    When I send the full payment lifecycle in reverse order for payment "pay_001"
    Then the payment "pay_001" status should be "settled"

  Scenario: Authorized payment can be declined in correct order
    Given a payment "pay_001" exists in "authorized" status
    When I send a "payment.declined" webhook for payment "pay_001"
    Then the response status should be 200
    And the payment "pay_001" status should be "declined"

  Scenario Outline: All valid state transitions are accepted
    Given a payment "pay_001" exists in "<initial_status>" status
    When I send a "<event_type>" webhook for payment "pay_001"
    Then the response status should be 200 or 202
    And the payment "pay_001" status should be "<expected_status>"

    Examples:
      | initial_status | event_type           | expected_status |
      | pending        | payment.authorized   | authorized      |
      | pending        | payment.declined     | declined        |
      | authorized     | payment.captured     | captured        |
      | authorized     | payment.declined     | declined        |
      | captured       | payment.settled      | settled         |
      | captured       | payment.refunded     | refunded        |
      | settled        | payment.refunded     | refunded        |
      | settled        | payment.chargeback   | chargebacked    |

  Scenario Outline: Invalid state transitions are rejected with 422
    Given a payment "pay_001" exists in "<initial_status>" status
    When I send a "<event_type>" webhook for payment "pay_001"
    Then the response status should be 422

    Examples:
      | initial_status | event_type           |
      | declined       | payment.authorized   |
      | declined       | payment.captured     |
      | chargebacked   | payment.refunded     |
      | refunded       | payment.captured     |
