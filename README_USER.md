# AIC 2026 user guide

For members who only use the website. You do not need Git, Docker, Python, Node.js or Jenkins.

## Reaching the website

### On the same Wi-Fi/LAN

Get the address from whoever operates the machine, for example:

```text
http://192.168.1.20:8088
```

Do not use `localhost:8088` — `localhost` always points at the machine running the browser.

Requirements:

- The production machine and its Docker stack are running.
- Your device is on the same Wi-Fi/LAN as that machine.
- The firewall allows inbound TCP on port `8088`.
- The Wi-Fi network does not enforce client/AP isolation.

### Over the internet

Once the system is deployed to a shared server, use the HTTPS domain the team provides, for example:

```text
https://aic2026.example.com
```

## Checking the system

Open the site in an up-to-date Chrome, Edge or Firefox. If the page does not load, check:

1. That the IP address or domain is correct.
2. That your device is on the same network as the production machine.
3. That the production machine is up.
4. Reload with `Ctrl + F5`.

## What works today

Visual search (BEiT-3 and Jina), OCR search and ASR search are available. The full feature set depends
on the operator having connected:

- MongoDB with the OCR/ASR corpus.
- The frame server and the keyframe images.
- Model checkpoints.
- Metadata and embeddings.

## Reporting a problem

Send the development team:

- When the error happened.
- The address you were using.
- The steps you took.
- The exact query you typed.
- What you expected and what you got.
- A screenshot or screen recording.

Never send passwords, API keys, MongoDB URIs or Jenkins credentials through group chat.

## Tools you do not need access to

- The GitHub repository: source code.
- Jenkins: automated test, build and deploy.
- GitHub Container Registry: Docker images.
- MongoDB and Qdrant: data and vectors.

Users only ever need the production website.
