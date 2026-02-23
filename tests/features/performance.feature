Feature: Performance and Timeout Handling
  As the FulfillHub payment system
  I want webhook processing to remain fast under load
  So that Yuno never retries due to timeouts

  Scenario: 100 concurrent webhooks for different payments all succeed
    Given 100 payments exist in "pending" status
    When I send 100 concurrent authorization webhooks for different payments
    Then no response should have a 5xx status code
    And all 100 payments should be in "authorized" status

  Scenario: P95 response time for sequential webhooks stays under 2 seconds
    Given 20 payments exist in "pending" status
    When I send 20 sequential authorization webhooks and measure response times
    Then the P95 response time should be under 2 seconds
