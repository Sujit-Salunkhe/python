
from  fastapi import FastAPI 
from fastapi import HTTPException

app = FastAPI(root_path="/api/v1")

data = [
    {
        "campaign_id": "1",
        "name": "Summer Sale Blitz",
        "due_date": "2026-02-15",
        "created_at": "2026-01-10T09:30:00Z",
        "status": "active",
        "budget": 25000,
        "clicks": 12450,
        "impressions": 156789,
        "conversions": 342,
        "platform": "Google Ads"
    },
    {
        "campaign_id": "2", 
        "name": "Black Friday Prep",
        "due_date": "2026-01-28",
        "created_at": "2026-01-12T14:22:00Z",
        "status": "paused",
        "budget": 45000,
        "clicks": 8560,
        "impressions": 98765,
        "conversions": 189,
        "platform": "Facebook Ads"
    },
    {
        "campaign_id": "3",
        "name": "Email Newsletter Q1",
        "due_date": "2026-02-05",
        "created_at": "2026-01-08T11:15:00Z",
        "status": "completed", 
        "budget": 8500,
        "clicks": 2345,
        "impressions": 45210,
        "conversions": 156,
        "platform": "Mailchimp"
    },
    {
        "campaign_id": "4",
        "name": "LinkedIn B2B Leads",
        "due_date": "2026-02-20",
        "created_at": "2026-01-15T16:45:00Z",
        "status": "active",
        "budget": 32000,
        "clicks": 6789,
        "impressions": 54321,
        "conversions": 89,
        "platform": "LinkedIn Ads"
    },
    {
        "campaign_id": "5",
        "name": "SEO Content Push",
        "due_date": "2026-03-01",
        "created_at": "2026-01-18T10:00:00Z", 
        "status": "draft",
        "budget": 15000,
        "clicks": 0,
        "impressions": 0,
        "conversions": 0,
        "platform": "Organic"
    }
]


@app.get('/')
async def root():
    return {"message: hello World"}


@app.get('/camgaigns')
async def read_capaigns():
    return (f"campaigns:${data}")


@app.get('/camgaigns/{id}')
async def read_campains_id(id):
    for campaingn in data:
        if campaingn.get("campaign_id") == id:
            return {f"campaing:${id}"}
    return HTTPException(status_code=404)




