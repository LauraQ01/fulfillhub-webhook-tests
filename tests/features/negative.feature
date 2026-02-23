Feature: Negative Testing and Malicious Payload Handling
  As the FulfillHub payment system
  I want to safely reject malformed, incomplete, and malicious webhook payloads
  So that bad input never causes unhandled server errors

  Background:
    Given a payment "pay_001" exists in "pending" status

  Scenario Outline: Webhooks missing required fields are rejected with 400
    When I send a "payment.authorized" webhook for payment "pay_001" without the "<field>" field
    Then the response status should be 400

    Examples:
      | field      |
      | webhook_id |
      | event_type |
      | data       |
      | payment_id |
      | amount     |
      | currency   |

  Scenario Outline: Webhooks with invalid field types are rejected with 422
    When I send a webhook with field "<field>" set to a "<wrong_type>" value
    Then the response status should be 422

    Examples:
      | field      | wrong_type |
      | amount     | string     |
      | webhook_id | integer    |

  Scenario Outline: Webhooks with invalid amount values are rejected with 422
    When I send a webhook with amount value "<amount_value>" for payment "pay_001"
    Then the response status should be 422

    Examples:
      | amount_value |
      | -100         |
      | 99999999999  |

  Scenario: SQL injection in payment_id field does not cause a server error
    When I send a webhook with payment_id set to "'; DROP TABLE payments; --"
    Then the response status should not be a 5xx error

  Scenario: Oversized 10MB payload is rejected
    When I send a webhook request with a 10 megabyte payload
    Then the response status should be 413 or 422

  Scenario: Deeply nested JSON payload does not crash the server
    When I send a webhook with 1000 levels of nested JSON
    Then the response status should not be a 5xx error

  Scenario Outline: Invalid or empty body formats are rejected
    When I send a request with a "<body_description>" as the body
    Then the response status should be 400 or 422

    Examples:
      | body_description |
      | non-JSON text    |
      | empty body       |
      | empty JSON {}    |

  Scenario: Unicode characters in text fields are handled safely
    When I send a valid webhook with unicode and emoji characters in the merchant_id
    Then the response status should not be a 5xx error

  Scenario: Webhook for a non-existent payment returns 404
    When I send a "payment.authorized" webhook for non-existent payment "pay_NONEXISTENT"
    Then the response status should be 404
