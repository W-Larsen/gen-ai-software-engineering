# Demo Files

## Start the API

```bash
./demo/run.sh
```

## Run sample requests (curl)

In another terminal (while API is running):

```bash
./demo/sample-requests.sh
```

Optional custom URL:

```bash
BASE_URL=http://localhost:3000 ./demo/sample-requests.sh
```

## REST Client file

Use `demo/sample-requests.http` with VS Code REST Client or a compatible HTTP client.

## Sample data

`demo/sample-data.json` contains reusable payloads and interest query values used by the sample script.
