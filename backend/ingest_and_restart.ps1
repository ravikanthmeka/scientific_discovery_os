Write-Host "Starting bulk ingestion for requested fields..."
Set-Location "C:\Users\Codewiz Nashua\geminiprojects\scientific_discovery_os\backend\ingestion"
& "C:\Users\Codewiz Nashua\geminiprojects\scientific_discovery_os\venv\Scripts\python.exe" bulk_ingest.py --max-papers 20

Write-Host "Ingestion complete. Restarting backend..."
Set-Location "C:\Users\Codewiz Nashua\geminiprojects\scientific_discovery_os\backend"
& "C:\Users\Codewiz Nashua\geminiprojects\scientific_discovery_os\venv\Scripts\python.exe" -m uvicorn main:app
