# Backend launch
cd 03_Backend
python3 backend.py A 3001 # Backend A (127.0.0.13 side)
python3 backend.py B 3002 # Backend B (127.0.0.14 side)

Endpoints: / /api/status /api/info
Header on every reply: X-Backend
