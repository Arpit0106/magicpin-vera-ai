import uvicorn
from fastapi import FastAPI
from app.api.endpoints import router as api_router

app = FastAPI(
    title="magicpin Vera AI Bot",
    description="A production-ready candidate bot for the magicpin Tech/Product AI Analyst Hiring Challenge.",
    version="1.0.0"
)

# Register routes
app.include_router(api_router)

if __name__ == "__main__":
    # Start the server locally
    # We will bind to port 8080 as configured in the judge simulator
    uvicorn.run("main:app", host="127.0.0.1", port=8080, reload=True)
