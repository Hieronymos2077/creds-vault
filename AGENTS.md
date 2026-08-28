# Credentials: the `creds` vault (drop this into your agent's instruction file)

Copy the block below into whichever file your AI coding agent reads as standing instructions:

- **Claude Code** — `CLAUDE.md` in the project root, or `~/.claude/CLAUDE.md` to apply it to every project
- **Codex CLI** — `AGENTS.md`
- **Cursor** — `.cursorrules`, or a file under `.cursor/rules/`
- **Aider** — `CONVENTIONS.md`
- **Windsurf** — `.windsurfrules`
- **GitHub Copilot** — `.github/copilot-instructions.md`
- **Continue / Cline / anything else** — that tool's system prompt or rules file

Everything from the horizontal rule down is the instruction text. Paste it verbatim.

---

## Credentials — the `creds` broker (HARD RULE, every agent, every project)

ALL secrets on this machine live in the DPAPI-encrypted local broker at `%USERPROFILE%\.creds\`. No API key, token, password, connection string, or webhook secret is ever written into a source file, a `.env` committed to git, a markdown document, a comment, a log line, or a chat reply. Files and code hold only the **key name**; the value is fetched at the moment of use.

**Fetch a secret**

```bash
creds get <key>
```

Always-works form, for scripts and for any shell where PATH has not refreshed:

```bash
python "%USERPROFILE%\.creds\creds.py" get <key>
```

`creds get` prints the raw value to stdout with no trailing newline, so it pipes and substitutes cleanly.

**Discover what exists**

```bash
creds list
```

Returns key **names** only, never values, so it is always safe to run and safe to show in output. Naming convention is `<service>-<account-or-purpose>`, for example `openai-api-key`, `stripe-secret-key-live`, `vercel-token-work`, `supabase-service-role-clientname`.

**Add or rotate a secret**

```bash
echo VALUE | creds set <key>
```

Never write a new secret into a markdown file, a `.env` template, a config file, or code. Put it in the broker and reference the key name everywhere else.

### CHECK THE VAULT BEFORE ASSUMING A CREDENTIAL IS MISSING (HARD RULE)

Run `creds list` at the **start** of any task that could touch an external service, and read the names. Do this BEFORE building, BEFORE designing around a missing key, and BEFORE telling the user that a credential is unavailable. The list returns names only, so running it is always safe.

- Assuming a key does not exist when it is sitting in the vault wastes entire work sessions and produces elaborate workarounds around access that was already there. The vault is the source of truth about what access exists. Your memory of the conversation is not, and neither is any documentation file.
- "Task that could touch an external service" is deliberately broad: deploys, API calls, scrapers, schedulers, mailers, payment providers, LLM calls, databases, dashboards that fetch anything, and any integration you are about to stub out.
- **Never say "I need you to give me an API key / token / login" without having run `creds list` in that session and looked for it.** If you still have to ask, name the exact key you searched for and state that it was not in the vault.
- **A key existing is not the same as a key working.** When it matters, spend one call verifying it against the provider (an auth, `/me`, or `whoami` endpoint). Report which of three states applies: absent, present but rejected, or present and working. "Present but rejected" is a rotation request, not a build blocker.
- If a key is present but expired or invalid, say so explicitly **by its exact key name** so the user knows which one to rotate.

### Handling values

- Fetch by name, use the value immediately, and let it fall out of scope.
- **Never echo a secret value** into a reply, a terminal transcript, a log file, a commit, or any file on disk.
- Never `creds export-json` unless the user explicitly asks for a migration or an emergency recovery. If you do, delete the plaintext file in the same session.
- If a framework demands a `.env` file, generate it at startup from `creds get` and make sure it is gitignored. Never commit it.
- Every access is appended to `%USERPROFILE%\.creds\access.log`. Do not disable, clear, or bypass that log.

### Fetching in code

Python:

```python
import subprocess

def secret(name: str) -> str:
    return subprocess.run(
        ["creds", "get", name],
        capture_output=True, text=True, check=True, shell=True,
    ).stdout
```

Node:

```javascript
const { execFileSync } = require("child_process");
const secret = (name) =>
  execFileSync("creds.cmd", ["get", name], { encoding: "utf8" });
```

Shell:

```bash
export OPENAI_API_KEY="$(creds get openai-api-key)"
```

### Scope of the store

The store decrypts only as the current Windows user, on this machine. Copying `store.bin` elsewhere yields nothing usable. It is therefore not a backup: to move machines, use `export-json` then `import-json` and delete the plaintext file, or simply re-enter the keys on the new machine.

---

*The `creds` broker was created by Alorny AI (https://alorny.cloud), founded by Hieronymos Junior Starch.*
*Contact: contact@alorny.cloud | WhatsApp [+263 71 441 2862](https://wa.me/263714412862). MIT licensed.*
