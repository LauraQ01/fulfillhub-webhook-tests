Feature: Idempotency and Retry Handling
  As the FulfillHub payment system
  I want duplicate webhook deliveries to be handled safely
  So that payments are never processed more than once

  Background:
    Given a payment "pay_001" exists in "pending" status

  Scenario: Duplicate webhook is processed only once
    When I send a "payment.authorized" webhook with id "wh-001" for payment "pay_001"
    And I send the same webhook with id "wh-001" again
    Then both responses should have status 200
    And there should be exactly 1 processed event for webhook "wh-001" in the database
    And the payment "pay_001" status should be "authorized"

  Scenario: Event is persisted in database before 200 is returned
    When I send a "payment.authorized" webhook with id "wh-persist" for payment "pay_001"
    Then the response status should be 200
    And event "wh-persist" should exist in the database with processing_status "processed"

  Scenario: Two different webhook ids for different payments are both processed
    Given a payment "pay_002" exists in "pending" status
    When I send a "payment.authorized" webhook with id "wh-aaa" for payment "pay_001"
    And I send a "payment.authorized" webhook with id "wh-bbb" for payment "pay_002"
    Then event "wh-aaa" should exist in the database with processing_status "processed"
    And event "wh-bbb" should exist in the database with processing_status "processed"

  Scenario: Concurrent identical webhooks are processed exactly once
    When I send 5 concurrent requests with webhook id "wh-race" for payment "pay_001"
    Then all responses should have a 2xx status
    And there should be exactly 1 processed event for webhook "wh-race" in the database

  Scenario: Legitimate retry from Yuno returns 200 not 409
    Given I successfully sent a "payment.authorized" webhook with id "wh-retry" for payment "pay_001"
    When I send the same webhook with id "wh-retry" again simulating a Yuno retry
    Then the response status should be 200
    And the response body should indicate it was an idempotent response
