from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import engine
from app import models
from app.routers import auth, products, cart, orders, admin

# Create all tables
models.Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="ShopWave API",
    description="Full-stack e-commerce backend with JWT auth, cart, and orders",
    version="1.0.0",
)

# CORS — allow frontend dev server + production S3 domain
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(products.router)
app.include_router(cart.router)
app.include_router(orders.router)
app.include_router(admin.router)


@app.get("/")
def root():
    return {
        "message": "ShopWave API is running 🛍️",
        "docs": "/docs",
    }


@app.on_event("startup")
def on_startup():
    from app.seed import seed
    seed()
