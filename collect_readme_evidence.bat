@echo off
echo === 1. Low risk ===
curl -s -X POST http://localhost:5000/submit -H "Content-Type: application/json" -d "{\"creator_id\": \"evidence-1\", \"text\": \"I went on two dates with him. He was polite, but we did not really click. I would not go out again, but nothing unsafe happened.\"}"
echo.
echo.
echo === 2. Privacy risk only ===
curl -s -X POST http://localhost:5000/submit -H "Content-Type: application/json" -d "{\"creator_id\": \"evidence-2\", \"text\": \"He works at ABC Bank on 57th Street and his phone number is 212-555-0198.\"}"
echo.
echo.
echo === 3. Defamation risk only ===
curl -s -X POST http://localhost:5000/submit -H "Content-Type: application/json" -d "{\"creator_id\": \"evidence-3\", \"text\": \"He is definitely a criminal and abuses every woman he dates. Everyone should avoid him.\"}"
echo.
echo.
echo === 4. Combined high risk (privacy + defamation) ===
curl -s -X POST http://localhost:5000/submit -H "Content-Type: application/json" -d "{\"creator_id\": \"evidence-4\", \"text\": \"He works at ABC Bank on 57th Street and I heard he has an STD. Everyone should avoid him.\"}"
echo.
echo.
echo === 5. AI-like (for the AI label + high vs low confidence comparison) ===
curl -s -X POST http://localhost:5000/submit -H "Content-Type: application/json" -d "{\"creator_id\": \"evidence-5\", \"text\": \"This individual demonstrates numerous red flags that should be carefully considered before engaging in a romantic relationship. It is important to prioritize personal safety and evaluate behavioral patterns objectively.\"}"
echo.
echo.
echo === Now copy the content_id from step 3 (defamation) and appeal it manually, then run: ===
echo curl -s http://localhost:5000/log