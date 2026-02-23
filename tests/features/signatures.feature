Feature: Webhook Signature Verification
  As the FulfillHub payment system
  I want to verify HMAC-SHA256 signatures on every incoming webhook
  So that forged or tampered webhooks are rejected

  Background:
    Given a payment "pay_001" exists in "pending" status

  Scenario: Valid HMAC-SHA256 signature is accepted
    When I send a "payment.authorized" webhook with a valid signature for payment "pay_001"
    Then the response status should be 200

  Scenario: Webhook signed with wrong secret is rejected
    When I send a "payment.authorized" webhook signed with an incorrect secret key
    Then the response status should be 401

  Scenario: Webhook with body tampered after signing is rejected
    When I send a "payment.authorized" webhook with the body modified after signing
    Then the response status should be 401

  Scenario Outline: Webhooks with missing or empty signature headers are rejected
    When I send a "payment.authorized" webhook with "<header_scenario>"
    Then the response status should be 401

    Examples:
      | header_scenario                   |
      | missing X-Yuno-Signature header   |
      | missing X-Yuno-Timestamp header   |
      | empty X-Yuno-Signature value      |

  Scenario: Signature older than 5 minutes is rejected as expired
    When I send a "payment.authorized" webhook with a signature that is 400 seconds old
    Then the response status should be 401

  Scenario: Signature within the 5-minute window is accepted
    When I send a "payment.authorized" webhook with a signature that is 299 seconds old
    Then the response status should be 200

  Scenario: Signature verification uses constant-time comparison to prevent timing attacks
    Then the signature verification implementation should use hmac.compare_digest
