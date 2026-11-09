# TaxSetu bridge for TallyPrime

This small program runs on your Windows PC beside TallyPrime. TaxSetu creates
drafts for a person to review and approve. The bridge checks the approved,
signed entries before sending them to the paired company's books. It does not
file tax returns. It needs Python 3.10 or newer; no extra Python packages.

1. Keep `tally_bridge.py` in a folder on the Tally PC. Open that folder in File
   Explorer, type `cmd` in the address bar, and press Enter.
2. Open TallyPrime. Press **F1 Help > Settings > Advanced Configuration**.
   Enable the HTTP server, choose port **9000**, and keep your company open.
   Keep this port local to your PC; do not expose it on the internet or router.
3. In TaxSetu, choose your company and get a bridge pairing code and API address.
   Run `python tally_bridge.py pair --api YOUR_API_ADDRESS --code YOUR_PAIRING_CODE`.
   Replace the two placeholders with the values shown in TaxSetu. The command
   `python tally_bridge.py pair` needs these two details to complete pairing.
4. Run `python tally_bridge.py selftest`. A **PASS** means Tally answered and
   the paired company was found. A **FAIL** explains what to check. A successful
   check also sends your ledger names, groups and GSTINs to your TaxSetu account.
5. To check approved entries without importing them, run
   `python tally_bridge.py once --dry-run`. This acknowledges those entries as
   `dry-run`, so they will need new human approval before a real import.
6. Run `python tally_bridge.py run`. Leave this window and TallyPrime open.
   The bridge checks every 15 seconds, retries network failures with increasing
   waits up to five minutes, and refreshes ledgers every 20 checks.

Only entries already approved in TaxSetu should reach this bridge. Confirm the
company and amounts in TaxSetu before approval. For a single check instead of
continuous running, use `python tally_bridge.py once`.

## Settings and logs

Settings are stored in `%USERPROFILE%\.taxsetu-bridge.json`, readable only by
your Windows account where supported. Do not share this file: it contains your
bridge token and signing key. If Windows refuses permission changes, the bridge
warns you; keep these files in a private user folder. The bridge never displays
the token or key. Pairing refuses
to overwrite an existing configuration or import history.

You can edit `tally_url` (normally `http://127.0.0.1:9000`), `poll_seconds`
(normally `15`), or `dry_run` (`true` or `false`) with Notepad while the bridge
is stopped. Keep `api_base`, `bridge_token`, `signing_key` and `company` as paired.
For a different settings location, add `--config "C:\your-folder\bridge.json"`
to each command. The folder must already exist. Use the same location each time.

Read messages in the command window or open
`%USERPROFILE%\.taxsetu-bridge.json.log` with Notepad. An older log is kept as
`.log.1`. Logs mask the token and signing key. Refused entries have a detailed
reason in TaxSetu. A network message means check your internet and Tally's HTTP
settings. Ledger sync failures do not stop imports.

The adjacent `.taxsetu-bridge.json.posted.json` file is the import history.
Keep it private and **do not delete or edit it to retry an entry**. It stores
results so a failed acknowledgement can be retried without importing twice.
The bridge records its intent before sending to Tally. If the PC stops or the
connection fails at that point, the result may say **Import outcome uncertain**.
Check the company's books with your accountant before preparing and approving
a replacement. The bridge deliberately never resends that item, even if the
interruption happened before Tally received it. Keep a backup of the history
with your settings; losing it can allow duplicate imports. History keeps item
IDs permanently and replies only until acknowledged, and grows with your imports.

## Stop or remove

Press **Ctrl+C** in the command window to stop. You can restart with the same
`run` command; saved acknowledgements resume. There is no background service or
automatic startup to uninstall. Only one bridge may use a settings file at once.

To remove it, stop the bridge, revoke/unpair it in TaxSetu, and delete the folder
containing `tally_bridge.py`. Retain your settings and import history privately
until all pending entries are reconciled. Then delete the settings, `.posted.json`,
`.lock`, `.log` and `.log.1` files from your user folder (or custom location).
This does not remove anything from Tally's books. Reconcile pending work before
pairing again.

The automated checks use simulated Tally servers. Validate the first real
installation with `selftest`, a dry run, and a small reviewed import with your
accountant; live TallyPrime and Windows versions may differ.
