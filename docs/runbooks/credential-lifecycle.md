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

## Bootstrap, reset, or rotate production credentials

Use the host wrapper instead of invoking `clothes-model-security` directly so every newly issued
plaintext token is persisted before the terminal session ends:

```powershell
./infra/manage-production-credentials.ps1 -Command bootstrap
./infra/manage-production-credentials.ps1 -Command reset-admin
./infra/manage-production-credentials.ps1 -Command rotate-app
```

The default file is
`%LOCALAPPDATA%\ClothesModel\production-credentials.json`. It is outside the repository, is replaced
atomically, and grants file access only to the current Windows user. The file keeps only the current
App/Admin token pair; a reset or rotation replaces the affected plaintext value instead of retaining
revoked token history. The script never prints token values to the console.

The file does not store Provider API keys or the encryption master key. Web Admin continues to use
the Admin Token only for the current login exchange and does not persist it in browser storage.

## Recovery when a credential is believed compromised

- App: rotate from Web Admin; Android re-authenticates on the next request.
- Admin: run `manage-production-credentials.ps1 -Command reset-admin` on the host if the current
  Admin Token is lost.

## Expected signals

- Old tokens return `401 unauthorized`.
- New tokens work; Android re-authentication restores history without cancelling jobs.
