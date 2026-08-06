# Local Aztek Full-Session Capture Design

**Date:** 2026-08-06  
**Status:** Approved direction, pending implementation plan

## Problem

The current bookmark pairing flow copies `document.cookie` and local storage
from an Aztek page. JavaScript cannot read `HttpOnly` cookies, so Dex/IPA SSO
cookies are missing from the saved Playwright `storage_state`. Pairing can look
successful, but the next Item Finder browser is redirected to IPA login. The
search runner then correctly marks that incomplete session as expired.

Repeating the same bookmark pairing cannot repair the session because it omits
the same protected cookies each time.

## Goals

- Give the Local Setup a reliable `เปิด Aztek และเชื่อม` action.
- Let the operator sign in manually in a visible Chromium window.
- Capture the complete Playwright storage state, including `HttpOnly` cookies.
- Reuse the existing encrypted, per-user Aztek session store.
- Keep the design ready for a future hosted Chrome extension without changing
  Item Finder or the other Aztek runners again.
- Do not store Aztek/IPA usernames or passwords.

## Non-goals

- This change does not bypass IPA, automate credentials, or extend an expired
  SSO session.
- It does not make the local direct-capture endpoint available on a deployed
  server.
- It does not create any Bundle, Item Code, Event, or Product record.
- It does not implement the future Chrome extension in this change.

## User experience

### Local Setup

The Aztek connection section shows one primary action:

`เปิด Aztek และเชื่อม`

When pressed:

1. The button becomes disabled and the page says that Chromium is open and is
   waiting for the operator to finish signing in.
2. The backend opens a visible Chromium window on a known read-only Aztek page.
3. The operator completes Dex/IPA login in that Chromium window.
4. The tool verifies that the same browser can open the Aztek application
   without returning to a login page.
5. The tool captures the full context with `context.storage_state()`, validates
   it, encrypts it, and replaces the operator's stored Aztek session.
6. Chromium closes, the page refreshes the connection status, and reports
   success.

If the operator closes Chromium early, login does not finish within five
minutes, or validation still reaches a login page, the page shows a clear Thai
error. The previously stored session is not overwritten.

Local mode hides the bookmark, pairing-token input, and pairing instructions so
there are not two competing connection methods.

### Hosted web app

Hosted mode keeps the existing pairing-token/bookmark interface for now and
does not show the local direct-capture button. Direct capture is deliberately
rejected server-side in hosted mode because a deployed server would open a
browser on the server machine, not on the operator's computer.

A future Chrome extension or local helper can capture the operator browser's
full session and submit it through the same storage service described below.

## Architecture

### 1. Shared session persistence

`AztekSessionService` gains one reusable operation that accepts an authenticated
user, a Playwright storage-state object, and an optional account label. It:

- runs the existing storage-state origin/domain/size validation;
- encrypts the state with the existing AES-GCM path;
- creates or replaces that user's `AztekSession`;
- sets the session status to `active`; and
- never returns ciphertext or cookie values to the client.

The existing pairing-token consumer first validates that its token is pending,
uses this shared persistence operation, and marks the token used only after the
session is stored successfully. The new local capture service uses the same
operation after its live-browser check succeeds. This is the seam a future
extension will reuse.

No database migration is required.

### 2. Local capture service

A small Playwright service owns the manual-login flow:

- launch headed Chromium with the existing Windows-safe launch options;
- create a fresh non-persistent browser context;
- open a known read-only Aztek v2 item-listing URL;
- wait for an allowed Aztek application origin with no visible login/password
  state;
- perform a final navigation/check in the same context to prove the SSO state
  works;
- call `context.storage_state()` only after that proof; and
- always close the page, context, and browser in `finally` cleanup.

The fresh context is intentional: it avoids reading or modifying the user's
normal Chrome profile and guarantees that the stored state is exactly the state
created during this connection attempt.

The capture timeout is five minutes. It is an awaited local HTTP request rather
than a background job: the FastAPI event loop remains responsive while
Playwright waits, and the UI needs only one request and one result.

### 3. Browser-operation gate

Application startup creates one shared async browser-operation gate using the
existing `BROWSER_CONCURRENCY` setting (one slot in Local Setup). Item Finder,
manual session capture, option fetches, previews, and create runners acquire
that gate before launching Chromium.

This prevents the login window from competing with a search or create preview.
If another browser task owns the slot, the connection page reports that it is
waiting. The button cannot start a second capture request while the first is in
progress.

### 4. API boundary

Add a session-authenticated endpoint:

`POST /api/aztek/local-capture`

Rules:

- available only when `LOCAL_DESKTOP_MODE=true`;
- requires the same loopback-authenticated local user as other Local Setup
  pages;
- returns `404` in hosted mode so the local-only capability is not advertised;
- returns only status/account-label/error metadata, never cookies or storage
  state;
- writes an audit record for success or failure without cookie values; and
- does not modify the stored session unless capture and validation both finish
  successfully.

The existing `/api/aztek/pair` endpoint remains available in hosted mode and
continues to enforce its short-lived, single-use pairing token.

## Failure handling

- **Window closed:** stop the attempt, clean up Playwright, keep old session.
- **Timeout:** stop after five minutes, clean up, keep old session.
- **Still on IPA/login:** report that login was not completed, keep old session.
- **Invalid/off-origin state:** reject through existing validation, keep old
  session.
- **Playwright launch error:** show a local actionable error and keep old
  session.
- **Successful reconnect after expiry:** replace encrypted state and set status
  back to `active`.

Item Finder keeps its current behavior of marking a session expired when a
later real search is redirected to login. Direct capture fixes the missing
session material; it does not suppress genuine expiry.

## Security and privacy

- Credentials are typed only into the Aztek/IPA page and are never submitted to
  All for Cabal.
- The tool captures only Playwright storage state for allowed Aztek/auth domains.
- Cookie values, storage state, pairing tokens, and encryption material are not
  logged or returned in API responses.
- The local-only endpoint is guarded both in the UI and on the server.
- No persistent user-data directory or normal Chrome profile is opened.

## Verification strategy

All automated tests use fake Playwright objects; no real Aztek login or record
creation is performed.

Required coverage:

- a successful local capture persists a state containing a simulated
  `HttpOnly` cookie and marks the session active;
- closing the browser, timeout, login redirect, and invalid state do not replace
  an existing session;
- hosted mode rejects the local endpoint before Playwright launches;
- pairing-token and local-capture paths both use the shared persistence method;
- local UI shows the direct button and hides bookmark pairing;
- hosted UI hides the direct button and retains bookmark pairing;
- UI waiting, success, and failure states are visible and the status refreshes;
- concurrent browser work respects the shared gate; and
- the full existing test suite remains green.

## Deployment consequence

This first implementation solves Local Setup only. When the app is deployed,
the server cannot directly capture the operator's browser session. Hosted use
will require a Chrome extension or trusted local helper that captures the full
session on the operator's machine and submits it through a pairing token. The
shared persistence boundary ensures that future addition will not require
changes to Item Finder, Bundle, Item Code, Event, or Product runners.
