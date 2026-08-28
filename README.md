# creds-vault

A tiny, offline, local secrets broker for AI coding agents on Windows.

Your API keys live encrypted on your own machine, bound to your Windows user account. Your agent never sees a key until the moment it needs one, it fetches by **name**, and every fetch is logged.

```bash
echo sk-live-abc123 | creds set stripe-secret-key
creds list
creds get stripe-secret-key
```

No cloud. No account. No network calls. One file of Python, no third-party packages.

---

## The problem it solves

AI coding agents (Claude Code, Codex, Cursor, Copilot, Aider, and the rest) need credentials constantly: deploy tokens, database URLs, LLM API keys, mail providers, payment processors. The usual habits are all bad:

| Habit | What goes wrong |
|---|---|
| Paste the key into the chat | It is now in a transcript, and probably in a model provider's logs |
| Put it in `.env` in the repo | One `git add .` away from a public leak, forever, in history |
| Keep a `credentials.md` | Plaintext on disk, readable by anything running as you |
| Hardcode it | It ships to production and to GitHub |
| Environment variables | Leak into child processes, crash dumps, and CI logs |

`creds-vault` replaces all of that with one rule: **secrets live in the vault, files and code hold only the key NAME.**

A commit can safely say `creds get stripe-secret-key`. It cannot leak anything, because the value is not there.

---

## How it works

1. Secrets go into a single JSON blob.
2. That blob is encrypted with the **Windows DPAPI** (`CryptProtectData`), which ties it to your Windows user account on that machine.
3. The ciphertext is written to `store.bin` next to the script.
4. Anything read or written is appended to `access.log`, so you have an audit trail of exactly which key was fetched, when, and by which process.

The consequence of DPAPI: copying `store.bin` to another PC, or to another Windows user, gives an attacker nothing. It will not decrypt. That is the point.

There is no master password to remember and no key file to lose. Your Windows login **is** the key.

---

## Install

Requires Windows and Python 3.8 or newer.

```powershell
git clone https://github.com/Hieronymos2077/creds-vault.git
cd creds-vault
powershell -ExecutionPolicy Bypass -File .\install.ps1
```

The installer copies `creds.py` and `creds.cmd` into `%USERPROFILE%\.creds`, adds that folder to your user PATH, and runs a real set/get/delete round trip to prove it works before it reports success.

Open a **new** terminal afterwards so the PATH change is picked up.

### Manual install

If you would rather not run the script:

```powershell
mkdir "$env:USERPROFILE\.creds"
copy creds.py  "$env:USERPROFILE\.creds\"
copy creds.cmd "$env:USERPROFILE\.creds\"
```

Then add `%USERPROFILE%\.creds` to your PATH, or just always call it by full path:

```bash
python "$env:USERPROFILE\.creds\creds.py" list
```

That full-path form always works even when PATH has not refreshed yet, so it is the safe form to put inside scripts and agent instructions.

---

## Commands

| Command | What it does |
|---|---|
| `creds set <key>` | Read the value from stdin. `echo VALUE \| creds set my-key` |
| `creds set <key> --value V` | Value on the command line. Convenient, but it lands in shell history, so avoid it for real secrets |
| `creds get <key>` | Print one value to stdout, with no trailing newline, so it pipes cleanly |
| `creds list [prefix]` | Print key **names** only, never values. Safe to run and safe to show anyone |
| `creds delete <key>` | Remove one key |
| `creds import-json <file>` | Bulk import from `{"key": "value", ...}`. Delete the plaintext file afterwards |
| `creds export-json <file>` | Decrypt everything into a plaintext JSON. Emergency and migration only |

A missing key exits with code `2` and suggests near matches, so a typo tells you what you meant instead of failing silently.

---

## Naming keys

Use `<service>-<account-or-purpose>`, lowercase, hyphen separated:

```
openai-api-key
anthropic-api-key-personal
stripe-secret-key-live
stripe-secret-key-test
supabase-service-role-clientname
vercel-token-work
github-pat-deploy
```

The names are the part your agent reads and reasons about, so make them describe **which** account and **which** environment. `stripe-key` is a bug waiting to happen when you have live and test. `stripe-secret-key-live` is not.

Because `creds list` never prints values, a well-named vault doubles as a readable inventory of every service you have access to.

---

## Using it from code

### Python

```python
import subprocess

def secret(name: str) -> str:
    return subprocess.run(
        ["creds", "get", name],
        capture_output=True, text=True, check=True, shell=True,
    ).stdout

api_key = secret("openai-api-key")
```

### Node

```javascript
const { execFileSync } = require("child_process");

const secret = (name) =>
  execFileSync("creds.cmd", ["get", name], { encoding: "utf8" });

const apiKey = secret("openai-api-key");
```

### Shell

```bash
export OPENAI_API_KEY="$(creds get openai-api-key)"
```

Fetch at the point of use, hold it in a local variable, and never write it to a file. If a value ends up in a `.env` for a framework that demands one, generate that `.env` at startup and gitignore it.

---

## Wiring it into your AI agent

This is the part that makes the vault actually pay off. Copy [`AGENTS.md`](AGENTS.md) into whichever instruction file your agent reads:

| Agent | File |
|---|---|
| Claude Code | `CLAUDE.md` (project root, or `~/.claude/CLAUDE.md` for every project) |
| Codex CLI | `AGENTS.md` |
| Cursor | `.cursorrules` or `.cursor/rules/` |
| Aider | `CONVENTIONS.md` |
| Windsurf | `.windsurfrules` |
| GitHub Copilot | `.github/copilot-instructions.md` |

The short version of what those instructions tell the agent:

- Run `creds list` at the start of any task that touches an external service, **before** deciding a credential is missing. The list is names only, so it is always safe to run.
- Fetch by name at the point of use. Never echo a value into a reply, a log, a commit, or a file.
- If a key genuinely is not there, name the exact key you searched for, then ask.

That last rule removes a specific, recurring waste: an agent assuming a credential does not exist, then building an elaborate workaround around a key that was sitting in the vault the whole time.

---

## The audit log

Every operation appends one tab separated line to `access.log`:

```
2026-08-28T14:02:11	get	openai-api-key	pid=18244	deploy-script
```

Set the `CREDS_CALLER` environment variable to tag which system made the call, and the last column tells you who asked:

```bash
CREDS_CALLER=nightly-deploy creds get vercel-token-work
```

Read it back whenever you want to know what a long-running agent actually touched:

```powershell
Get-Content "$env:USERPROFILE\.creds\access.log" -Tail 40
```

`get-MISS` lines are worth watching. A repeated miss on one name usually means a script and the vault disagree about spelling.

---

## Security, honestly stated

**What this protects against**

- Secrets committed to git, pasted into chat transcripts, or left in plaintext files
- A stolen laptop drive, or a copied `store.bin`. Neither decrypts on another machine or another Windows user
- Silent credential use, since every access is logged
- Agents inventing workarounds around keys you already own

**What this does not protect against**

- Malware already running as your Windows user. It can call the same DPAPI you can. No user-level secret store on any OS survives this. That includes the Windows Credential Manager, the macOS Keychain, and every password manager while it is unlocked
- Someone with your Windows password, sitting at your unlocked machine
- A secret you fetched and then wrote into a file yourself

**It is deliberately not**

- A team secret manager. It is single-user by design. For a team, use Vault, Doppler, 1Password, or your cloud provider's secret manager
- Cross platform. DPAPI is a Windows API. macOS and Linux ports would use Keychain and libsecret, and contributions are welcome
- A production runtime secret store. Use your platform's own for deployed services. This is for your development machine and your local agents

**Practical rules**

- `store.bin` and `access.log` are gitignored in this repo, and they should never be committed anywhere
- Delete any file made by `export-json` the moment you are done with it
- Prefer `echo VALUE | creds set key` over `--value`, because the second form lands in shell history
- Back the store up by re-entering the keys on the new machine, not by copying `store.bin`. It will not decrypt there anyway

---

## FAQ

**What if I lose my Windows account?**
The store cannot be decrypted. That is the intended trade off. Keep your keys recoverable from the providers themselves, since every one of them can reissue.

**Can I move it to a new PC?**
Run `export-json` on the old machine, `import-json` on the new one, then delete the plaintext file. Never copy `store.bin`.

**Does it work in WSL, Git Bash, or PowerShell?**
Git Bash and PowerShell, yes, since both reach the Windows Python. WSL cannot reach DPAPI directly. Call the Windows Python from WSL, or keep credential fetches on the Windows side.

**Why not just use the Windows Credential Manager?**
It is fine, and it uses the same DPAPI underneath. This gives a flat, greppable namespace, a portable single file, an audit log, and one command shape an agent can be taught in one line. Twenty keys in Credential Manager is a click marathon. Here it is `creds list`.

**Can two agents read it at once?**
Yes. Reads are independent. Writes replace the file atomically via `os.replace`, so a concurrent write cannot leave a half-written store.

---

## License

MIT. See [LICENSE](LICENSE). Use it, fork it, ship it commercially. No attribution required, though it is appreciated.

---

## Credits

Created by **Alorny AI**, founded by **Hieronymos Junior Starch**.

Alorny AI builds AI agents, automation systems and websites for businesses that would rather ship than fiddle.

- Website: [alorny.cloud](https://alorny.cloud)
- Email: [contact@alorny.cloud](mailto:contact@alorny.cloud)
- WhatsApp: [+263 71 441 2862](https://wa.me/263714412862)
- Phone: [+263 71 441 2862](tel:+263714412862)
- GitHub: [@Hieronymos2077](https://github.com/Hieronymos2077)

If this saved you from leaking a key, a star costs nothing.
