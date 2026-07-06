@echo off
echo Sending 12 rapid requests to /submit ...
echo Expect: first 10 = 200, last 2 = 429
echo.
for /l %%i in (1,1,12) do (
  curl -s -o nul -w "Request %%i: %%{http_code}\n" -X POST http://localhost:5000/submit -H "Content-Type: application/json" -d "{\"text\": \"This is a test submission for rate limit testing purposes only.\", \"creator_id\": \"ratelimit-test\"}"
)