from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pydantic import BaseModel
from sqlmodel import create_engine ,SQLModel,Session,Field, select
from fastapi import FastAPI, HTTPException, Depends
from typing import Annotated, Any, Generic, TypeVar
from  random import randint

class Campaign(SQLModel,table=True):
    campaign_id:int | None = Field(default=None,primary_key=True) 
    name:str = Field(index=True)
    due_date: datetime | None = Field(default=None,index=True)
    created_at:datetime = Field(default_factory=lambda:datetime.now(timezone.utc),nullable=True,index=True)


sqlite_file_name = "database.db"
sqlite_url = f"sqlite:///{sqlite_file_name}"

connect_args = {"check_same_thread":False}
engine = create_engine(sqlite_url,connect_args=connect_args)

def create_db_and_tables():
    SQLModel.metadata.create_all(engine)

def get_session():
    with Session(engine) as session:
        yield  session



SessionDep = Annotated[Session, Depends(get_session)]

@asynccontextmanager
async def lifespan(app:FastAPI):
    create_db_and_tables()
    with Session(engine) as session:
        if not session.exec(select(Campaign)).first():
            session.add_all([ 
                Campaign(name="summer Launch",due_date=datetime.now()),
                Campaign(name="Black Friday",due_date=datetime.now())
           ])
            session.commit()
    yield

app = FastAPI(root_path="/api/v1",lifespan=lifespan)



data:Any = [
    {
        "campaign_id": "1",
        "name": "Summer Sale Blitz",
        "due_date": "2026-02-15",
        "created_at": "2026-01-10T09:30:00Z",
       
    },
    {
        "campaign_id": "2", 
        "name": "Black Friday Prep",
        "due_date": "2026-01-28",
        "created_at": "2026-01-12T14:22:00Z",
    },
    {
        "campaign_id": "3",
        "name": "Email Newsletter Q1",
        "due_date": "2026-02-05",
        "created_at": "2026-01-08T11:15:00Z",
    },
    {
        "campaign_id": "4",
        "name": "LinkedIn B2B Leads",
        "due_date": "2026-02-20",
        "created_at": "2026-01-15T16:45:00Z",
    },
    {
        "campaign_id": "5",
        "name": "SEO Content Push",
        "due_date": "2026-03-01",
        "created_at": "2026-01-18T10:00:00Z", 
    }
]

T = TypeVar("T")
class Response(BaseModel,Generic[T]):
    data: T
    
@app.get('/campaigns',response_model = Response[list[Campaign]])
async def read_campaigns(session:SessionDep):
    data =  session.exec(select(Campaign)).all()
    return {"data":data}



@app.get('/')
async def root():
    return {"message": "hello World"}  

@app.get('/campaigns/{id}',respons_model=Response[Campaign])
async def read_campaign(id:int,session:SessionDep):
    data = session.get(Campaign,id)
    if not data:
        raise HTTPException(404)
    return {"data":data}


# @app.get('/campaigns')  
# async def read_campaigns():  
#     return data  

# @app.get('/campaigns/{id}')  
# async def read_campaign_id(id: str):  
#     for campaign in data:
#         if campaign.get("campaign_id") == id:
#             return campaign  
#     raise HTTPException(404, "We don't have such data")  

# @app.post("/campaigns")
# async def create_campaign(body: dict[str,Any]):
#   print(body,"body")
#   new:Any = {
#         "campaign_id": randint(100,1001),
#         "name": body.get("name"),
#         "due_date":body.get("due_date"),
#         "created_at": "2026-01-10T09:30:00Z",
#         "status": "active",
#         "budget": 25000,
#         "clicks": 12450,
#         "impressions": 156789,
#         "conversions": 342,
#         "platform": "Google Ads"
#     }
#   data.append(new)

#   return {"campaign":data}

# @app.put('/campaigns/{id}')
# async def update_campaign(id: int, body:dict[str,Any]):  

    
#     for index, campaign in enumerate(data):
#         if campaign.get('campaign_id') == str(id):  
#             updated: Any = {
#                 "campaign_id": str(id),
#                 "name": body.get("name", campaign.get("name")), 
#                 "due_date": body.get("due_date", campaign.get("due_date")),
#                 "created_at": campaign.get("created_at"),  
#                 "status": body.get("status", campaign.get("status")),
#                 "budget": body.get("budget", campaign.get("budget")),
#                 "clicks": campaign.get("clicks"),
#                 "impressions": campaign.get("impressions"),
#                 "conversions": campaign.get("conversions"),
#                 "platform": body.get("platform", campaign.get("platform"))
#             }
            
#             data[index] = updated
#             return updated 
    
#     raise HTTPException(404, "Campaign not found")  

# @app.delete('/campaigns/{id}')
# async def update_campaign(id: int):
#     for index,campaign in enumerate(data):
#         if campaign.get("campaign_id") == str(id):
#             data.pop(index)
           
#             return  {"message": "updated successfully", "campaign_id": id}
#     raise HTTPException(404,"Not Found")

