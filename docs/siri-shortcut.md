# Vault 966 Siri Shortcut

Use this to get voice responses from the `/api/assistant` endpoint on your local network.

## Prereqs
- Server running on your LAN: `uvicorn api.main:app --host 0.0.0.0 --port 8000`
- `ASSISTANT_API_TOKEN` set in `.env`
- Your Mac's LAN IP (example: `192.168.1.20`)

## Shortcut (recommended, POST)
1) Action: **Ask for Input**
   - Prompt: "What are you in the mood for?"
   - Type: Text
   - Save as variable `Query`

2) Action: **Get Contents of URL**
   - URL: `http://<LAN-IP>:8000/api/assistant?format=text`
   - Method: `POST`
   - Headers:
     - `Authorization: Bearer <ASSISTANT_API_TOKEN>`
     - `Content-Type: application/json`
   - Request Body (JSON):
     ```json
     {"query":"${Query}","limit":3}
     ```

3) Action: **Speak Text**
   - Speak the output of the previous action.

## Shortcut (simple, GET)
1) Action: **Ask for Input** (same as above)
2) Action: **Get Contents of URL**
   - URL: `http://<LAN-IP>:8000/api/assistant?format=text&q=${Query}&limit=3`
   - Method: `GET`
   - Headers:
     - `Authorization: Bearer <ASSISTANT_API_TOKEN>`
3) Action: **Speak Text**

## Notes
- Use `format=text` for a clean, voice-friendly reply.
- Keep queries short for best voice accuracy.
