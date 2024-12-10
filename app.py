import os
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from jinja2 import Template, Environment, FileSystemLoader
from pydantic import BaseModel
from typing import List, Optional
from elasticsearch import Elasticsearch

import modules

app = FastAPI()

## set ES connection
es = Elasticsearch(['http://modb-elasticsearch-datalake-explorer.brave-foundry.net:9200'], 
                    request_timeout=100, 
                    basic_auth=('modb', os.environ['es_pwd']))

# Mount static files directory
app.mount("/static", StaticFiles(directory="static"), name="static")

# Set up templates
templates = Environment(loader=FileSystemLoader("templates"))

# Add Model
class TrialFilters(BaseModel):
    phases: Optional[List[str]] = []
    status: Optional[List[str]] = []
    study_type: Optional[str] = None
    industry_sponsor: Optional[str] = None
    mesh_condition: Optional[List[str]] = []

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    conditions = modules.get_mesh_conditions()
    template = templates.get_template("index.html")
    return template.render(conditions=sorted(conditions))

@app.post("/trials")
async def get_trials(filters: TrialFilters):
    res = modules.run_es_query(es,filters)
    return {
        "data": res["trials"],
        "drug_counts": res["drug_counts"]
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=5000)