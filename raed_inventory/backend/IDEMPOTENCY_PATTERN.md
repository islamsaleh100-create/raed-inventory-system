# Idempotency Pattern

This project uses a shared idempotency pattern for high-impact mutations.

## Current protected operations

- `orders.submit_to_warehouse`
- `orders.dispatch`
- `orders.receive`

## Request contract

Clients send:

- `X-Client-Request-Id`

The backend enforces uniqueness using:

- `tenant_id`
- `client_request_id`
- `operation_name`

## Storage model

The `idempotency_requests` table stores:

- unique key: `(tenant_id, client_request_id, operation_name)`
- `response_reference_type`
- `response_reference_id`
- optional `request_hash`
- `expires_at`

Default expiry window:

- `48 hours`

## Endpoint implementation steps

For any new mutation:

1. Read `X-Client-Request-Id` from the request.
2. Look up an existing completed idempotency record before validating mutable status transitions.
3. If found, replay the previous logical response.
4. If not found, register a new pending idempotency record.
5. Execute the mutation once.
6. Complete the record with `response_reference_type` and `response_reference_id`.
7. Return the normal response payload.

## Replay rule

Replay should return the same logical result, not re-run stock or workflow side effects.

That means repeated requests must not:

- update stock twice
- create duplicate stock transactions
- advance workflow twice

## Cleanup

Expired idempotency records are cleaned by the background cleanup loop started from app startup.

## Testing rule

Every protected mutation must have an end-to-end test proving that:

- the first request succeeds
- the second identical request returns a replay response
- side effects happen only once
