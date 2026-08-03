# SellMate Pi Touchscreen — Architecture (Milestone 1)

## Role

Customer-facing fullscreen kiosk on a Raspberry Pi 10.1" touchscreen.

- Talks to **SellMateCloud** for orders/payment status.
- Reads **Firestore** inventory/planogram for product display.
- **Never** calls local vend-api, motors, ToF, claim, or complete.

Physical vend remains: Cloud → `sellmate-poller` → `vend-api`.

## Layers

| Layer | Package | Responsibility |
|---|---|---|
| UI | `app/ui` | PySide6 screens; no network I/O on UI thread |
| Workers | `app/ui/workers.py` | QThreads for Cloud/Firestore |
| State | `app/state` | Screen FSM, checkout orchestration, active-order persistence |
| API | `app/api` | Cloud HTTP client, Firestore inventory client |
| Models | `app/models` | Product, cart, order status mapping |
| Config | `app/config.py` | Env + `/etc/sellmate/machine.env` |
| Cache | inventory JSON under data dir | Startup/display resilience |
| Logging | `app/logging_setup.py` | Structured JSON; no secrets |

## Screen / state flow

```text
Boot → Attract → Browse ⇄ ProductDetail → Cart → Payment → Success/Failure → Attract
                     ↑ idle 90s clears cart ─────────────────────────────────────┘
```

On boot, if `active_order.json` references a non-terminal order, resume **Payment** polling before allowing a new checkout.

## Order statuses (primary)

`CREATED` → `AUTHORIZING` → `AUTHORIZED` → `VENDING` → `COMPLETED`  
Failures: `PAYMENT_FAILED`, `FAILED`, `CANCELLED`

Legacy Android aliases (`PAID`, `PAYMENT_STARTED`, …) map into the primary model.

**Cancel** allowed only for `CREATED` / `AUTHORIZING`.  
`AUTHORIZED` is **not** cancellable in the UI: Cloud has already created a `PENDING` vend_job, and cancel races with Pi claim (Cloud does not transactionally block claim).

## Checkout gate

Checkout requires:

1. Cloud `GET /health` reachable  
2. Inventory snapshot age ≤ `INVENTORY_MAX_AGE_SECONDS`

Cached inventory may display products; stale cache blocks checkout.

## Identity

Reuse `/etc/sellmate/machine.env` (`MACHINE_ID`, `CLOUD_BASE`) — same file as Pi poller/health.

## Out of scope (Milestone 1)

- Hardware control, health reporting, kiosk auth, multi-language, bundled fonts
