# ATLAS API Reference

The ATLAS backend provides a versioned RESTful API. All endpoints are prefixed with `/api/v1`. The API is designed to be consumed by the Android client and other authorized services.

## Base URL
`http://localhost:8000/api/v1`

## Authentication
Currently, the API supports open access for development. Future iterations will implement JWT-based authentication.

## Endpoints

| Endpoint | Method | Description | Status |
| :--- | :--- | :--- | :--- |
| `/health` | GET | Check system status and version. | Implemented |
| `/chat` | POST | Send a message to the AI assistant. | Placeholder |
| `/memory` | GET | Retrieve stored facts and context. | Placeholder |
| `/tasks` | POST | Manage personal tasks and projects. | Placeholder |
| `/voice` | POST | Process audio input for STT/TTS. | Placeholder |

## Health Check

**Request:**
`GET /health`

**Response (200 OK):**
```json
{
  "status": "ok",
  "project": "ATLAS",
  "version": "0.1.0"
}
```

## Error Handling

The API uses standard HTTP status codes to indicate the success or failure of requests. Errors are returned in a structured JSON format.

| Code | Meaning | Description |
| :--- | :--- | :--- |
| 200 | OK | Request succeeded. |
| 400 | Bad Request | Invalid parameters or payload. |
| 401 | Unauthorized | Authentication failed. |
| 404 | Not Found | Resource does not exist. |
| 500 | Internal Error | Server-side failure. |
