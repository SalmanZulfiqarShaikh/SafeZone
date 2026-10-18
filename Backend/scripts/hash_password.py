"""Turn a password into the hash that belongs in ADMIN_PASSWORD_HASH.

Run from ``Backend/``::

    python -m scripts.hash_password

It prompts without echoing, so the password never appears in your terminal
history, in a screenshot, or in a file. Paste the printed line into ``.env``,
which is gitignored.

The password itself is never written anywhere by this script. That is the
point: the repository is public (AGENTS.md 12), and a hash is useless to
anyone who finds it, while a password is not.
"""

from __future__ import annotations

import getpass
import secrets
import sys


def main(argv: list[str] | None = None) -> int:
    from core.auth import hash_password

    args = list(sys.argv[1:] if argv is None else argv)
    if args and args[0] in ("-h", "--help"):
        print(__doc__)
        return 0

    print("This prints two lines for your .env. The password is not stored.\n")

    password = getpass.getpass("Password: ")
    if not password:
        print("Nothing entered. Stopping.", file=sys.stderr)
        return 1

    if password != getpass.getpass("Again: "):
        print("The two did not match. Stopping.", file=sys.stderr)
        return 1

    if len(password) < 12:
        # Said once, not enforced: a short password on a demo is the team's
        # call, but they should make it knowingly.
        print(
            f"\nNote: that is {len(password)} characters. Anything reachable "
            "from the internet deserves 12 or more.\n",
            file=sys.stderr,
        )

    print("\nAdd these to Backend/.env:\n")
    print(f"ADMIN_PASSWORD_HASH={hash_password(password)}")
    print(f"SESSION_SECRET={secrets.token_urlsafe(48)}")
    print("\nAnd set ADMIN_EMAIL to the address you will log in with.")
    print("Changing SESSION_SECRET signs everyone out, which is how you")
    print("revoke a session before it expires.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
