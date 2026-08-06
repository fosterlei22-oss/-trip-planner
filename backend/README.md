# Backend

Run the API:

```bash
python -m uvicorn app.main:app --reload --port 8000
```

Main endpoint:

```text
POST /api/trip/plan
```

The backend mirrors the chapter 13 project idea with three lightweight agents:

- `DestinationResearchAgent`: picks destination places.
- `ItineraryAgent`: arranges day-by-day itinerary.
- `BudgetAgent`: estimates cost.
