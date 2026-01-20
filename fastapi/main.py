from fastapi import FastAPI, HTTPException, Response
import random
from typing import Any
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
    return {"message": "hello World"}  

@app.get('/campaigns')  
async def read_campaigns():  
    return data  

@app.get('/campaigns/{id}')  
async def read_campaign_id(id: str):  
    for campaign in data:
        if campaign.get("campaign_id") == id:
            return campaign  
    raise HTTPException(404, "We don't have such data")  


@app.post("/campaigns")
async def create_campaign(body: dict[str,Any]):
  print(body,"body")
  new:Any = {
        "campaign_id": random.randint(100,1001),
        "name": body.get("name"),
        "due_date":body.get("due_date"),
        "created_at": "2026-01-10T09:30:00Z",
        "status": "active",
        "budget": 25000,
        "clicks": 12450,
        "impressions": 156789,
        "conversions": 342,
        "platform": "Google Ads"
    }
  data.append(new)

  return {"campaign":data}



@app.put('/campaigns/{id}')
async def update_campaign(id: int, body:dict[str,Any]):  

    
    for index, campaign in enumerate(data):
        if campaign.get('campaign_id') == str(id):  
            updated: Any = {
                "campaign_id": str(id),
                "name": body.get("name", campaign.get("name")), 
                "due_date": body.get("due_date", campaign.get("due_date")),
                "created_at": campaign.get("created_at"),  
                "status": body.get("status", campaign.get("status")),
                "budget": body.get("budget", campaign.get("budget")),
                "clicks": campaign.get("clicks"),
                "impressions": campaign.get("impressions"),
                "conversions": campaign.get("conversions"),
                "platform": body.get("platform", campaign.get("platform"))
            }
            
            data[index] = updated
            return updated 
    
    raise HTTPException(404, "Campaign not found")  


@app.delete('/campaigns/{id}')
async def update_campaign(id: int):
    for index,campaign in enumerate(data):
        if campaign.get("campaign_id") == str(id):
            data.pop(index)
           
            return  {"message": "updated successfully", "campaign_id": id}
    raise HTTPException(404,"Not Found")