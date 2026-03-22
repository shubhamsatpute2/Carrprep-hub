# Job Search Configuration

CareerPrep Hub includes a job search feature that lets authenticated users search for jobs using
Google's Custom Search JSON API. The backend exposes an endpoint at `/api/jobs/search` which (note the `/api` prefix)
forwards queries to Google and returns a list of matching results.

## Prerequisites

- A Google account
- A Google Custom Search Engine configured to search job listings or the web in general
- API key for Google Custom Search

## Steps to Configure

1. **Create a Google Custom Search Engine**
   - Visit https://cse.google.com/cse/
   - Create a new search engine; you can restrict it to specific sites (e.g. `indeed.com`) or leave
     it to search the entire web. You will receive a `Search engine ID` (also called `cx`).

2. **Obtain an API Key**
   - Go to https://console.developers.google.com/
   - Enable the "Custom Search API" under "Library"
   - Navigate to "Credentials" and create an API key

3. **Set Environment Variables**
   In the backend `.env` file, add the following entries:

   ```env
   GOOGLE_API_KEY=your_google_api_key_here
   GOOGLE_CSE_ID=your_custom_search_engine_id_here
   ```

   These variables are read by `backend/app.py` when the server starts. If either is missing the
   `/api/jobs/search` endpoint will return a 500 error with a message indicating it is not
   configured.

## Usage

- The frontend component `JobSearch` provides a simple search box that sends requests to the
  backend endpoint.
- Requests must include a valid bearer token obtained after login; the component handles this
  automatically.
- Example HTTP request:

```http
GET /api/jobs/search?q=frontend+developer HTTP/1.1
Authorization: Bearer <token>
```


*Note:* This feature relies on an external API and will only work when the environment variables
are correctly set. You can test the endpoint using `curl` or Postman once the server is running.
