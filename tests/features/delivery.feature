Feature: Webhook Delivery and Response Validation
  As the FulfillHub payment system
  I want to correctly receive and respond to Yuno payment webhooks
  So that orders are processed reliably in real time

  Background:
    Given a payment "pay_001" exists in "pending" status

  Scenario Outline: Valid event types are accepted
    When I send a valid "<event_type>" webhook for payment "pay_001"
    Then the response status should be 200
    And the response body should contain the webhook_id
    And the response Content-Type should be application/json

    Examples:
      | event_type           |
      | payment.authorized   |
      | payment.captured     |
      | payment.declined     |
      | payment.settled      |
      | payment.refunded     |
      | payment.chargeback   |

  Scenario: Unknown event type is rejected
    When I send a webhook with event type "payment.exploded" for payment "pay_001"
    Then the response status should be 422

  Scenario: Ten sequential webhooks each respond within the 5 second SLA
    Given 10 payments exist in "pending" status
    When I send 10 sequential authorization webhooks one by one
    Then each response should complete within 5 seconds
    And all responses should have status 200
