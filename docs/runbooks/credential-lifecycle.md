# Runbook: Credential lifecycle

Goal: initialize, rotate, and recover the App Token and Admin Token without exposing secrets.

## Facts

- Only credential hashes are stored; a lost plaintext token cannot be recovered.
- Rotating the App Token immediately invalidates the previous token; server-side work continues.
- The Admin Token has no web rotation; recovery is a server-side/SSH operation.

## Rotate the App Token (preferred, through Web Admin)

1. Open Web Admin → `运行维护 / Token & Security`.
2. Confirm the rotation impact (old token invalid now, Android must re-authenticate, tasks continue).
3. Copy the one-time token from the dialog and save it; the dialog requires an explicit
   "saved" acknowledgement and never shows the value again.
4. Update connected Android installations.

## Recover a lost Admin Token or reset both (development)

```powershell
./infra/reset-development-credentials.ps1
```

Writes both new credentials to an operator-owned file outside the repository. Do not run during normal
startup and never commit the output.

## Recovery when a credential is believed compromised

- App: rotate from Web Admin; Android re-authenticates on the next request.
- Admin: rotate from Web Admin after re-authenticating; reset via SSH if the current Admin Token is
  lost.

## Expected signals

- Old tokens return `401 unauthorized`.
- New tokens work; Android re-authentication restores history without cancelling jobs.
