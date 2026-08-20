from fastapi import FastAPI, Query
from typing import Optional

app = FastAPI()

@app.get("/")
def root():
    return {"message": "API Running"}

@app.get("/shopii")
def shopii(
    cc: str = Query(...),
    site: str = Query(...),
    proxy: Optional[str] = Query(None)
):
    return {"cc": cc, "site": site, "proxy": proxy}
