import time

from pymongo.errors import PyMongoError

from src.mongo_connection import client

MAX_WAIT_SECONDS = 240
REQUIRED_STABLE_CHECKS = 10
CHECK_INTERVAL_SECONDS = 1


def main():
    deadline = time.monotonic() + MAX_WAIT_SECONDS
    stable_checks = 0
    last_message_at = 0.0

    print("Waiting for MongoDB to become a stable writable primary...")

    while time.monotonic() < deadline:
        try:
            hello = client.admin.command("hello")
            is_writable_primary = bool(
                hello.get("isWritablePrimary", False)
                or hello.get("ismaster", False)
            )

            if is_writable_primary:
                stable_checks += 1
                print(
                    f"MongoDB writable primary: "
                    f"{stable_checks}/{REQUIRED_STABLE_CHECKS} stable checks"
                )

                if stable_checks >= REQUIRED_STABLE_CHECKS:
                    # One final write-capability check against the admin DB.
                    client.admin.command("ping")
                    print("MongoDB is stable and ready for writes.")
                    return
            else:
                stable_checks = 0

        except PyMongoError as exc:
            stable_checks = 0
            now = time.monotonic()
            if now - last_message_at >= 5:
                print(f"MongoDB not writable yet: {type(exc).__name__}: {exc}")
                last_message_at = now

        time.sleep(CHECK_INTERVAL_SECONDS)

    raise SystemExit(
        f"MongoDB did not become a stable writable primary within "
        f"{MAX_WAIT_SECONDS} seconds."
    )


if __name__ == "__main__":
    main()
