"""
Seed script — run once to populate the database with products.
Usage: python -m app.seed
"""
from app.database import SessionLocal, engine
from app import models

models.Base.metadata.create_all(bind=engine)

PRODUCTS = [
    # Electronics
    {"name": "Sony WH-1000XM5 Headphones", "description": "Industry-leading noise canceling headphones with 30-hour battery life and crystal-clear call quality.", "price": 279.99, "category": "Electronics", "image_url": "https://images.unsplash.com/photo-1505740420928-5e560c06d30e?w=600", "stock": 45, "rating": 4.8, "review_count": 2341},
    {"name": "Apple AirPods Pro (2nd Gen)", "description": "Active noise cancellation, Adaptive Transparency, and Personalized Spatial Audio with dynamic head tracking.", "price": 199.99, "category": "Electronics", "image_url": "https://images.unsplash.com/photo-1572635196237-14b3f281503f?w=600", "stock": 80, "rating": 4.7, "review_count": 5621},
    {"name": "Logitech MX Master 3S Mouse", "description": "Advanced wireless mouse with ultra-fast MagSpeed scrolling and 8K DPI tracking on any surface.", "price": 89.99, "category": "Electronics", "image_url": "https://images.unsplash.com/photo-1527864550417-7fd91fc51a46?w=600", "stock": 120, "rating": 4.9, "review_count": 1876},
    {"name": "Samsung 27\" 4K Monitor", "description": "Ultra HD IPS panel with HDR400, 99% sRGB color accuracy, and USB-C connectivity.", "price": 449.99, "category": "Electronics", "image_url": "https://images.unsplash.com/photo-1527443224154-c4a3942d3acf?w=600", "stock": 30, "rating": 4.6, "review_count": 892},
    {"name": "Anker 65W GaN Charger", "description": "Compact 3-port charger with PowerIQ 3.0, charges a MacBook Pro at full speed.", "price": 35.99, "category": "Electronics", "image_url": "https://images.unsplash.com/photo-1558618666-fcd25c85cd64?w=600", "stock": 200, "rating": 4.7, "review_count": 3210},
    {"name": "Kindle Paperwhite (16GB)", "description": "6.8\" display, adjustable warm light, waterproof, weeks of battery life — the ultimate reading device.", "price": 139.99, "category": "Electronics", "image_url": "https://images.unsplash.com/photo-1592750475338-74b7b21085ab?w=600", "stock": 65, "rating": 4.8, "review_count": 7843},

    # Clothing
    {"name": "Uniqlo Ultra Light Down Jacket", "description": "Packable puffer jacket that weighs just 270g. Warmth without the bulk — perfect for travel.", "price": 79.99, "category": "Clothing", "image_url": "https://images.unsplash.com/photo-1551698618-1dfe5d97d256?w=600", "stock": 90, "rating": 4.6, "review_count": 1234},
    {"name": "Levi's 511 Slim Jeans", "description": "The iconic slim fit in sustainable stretch denim. Sits below waist, slim through hip and thigh.", "price": 59.99, "category": "Clothing", "image_url": "https://images.unsplash.com/photo-1542272604-787c3835535d?w=600", "stock": 150, "rating": 4.5, "review_count": 4567},
    {"name": "Nike Dri-FIT Training Tee", "description": "Lightweight sweat-wicking fabric keeps you dry during intense workouts. Regular fit for unrestricted movement.", "price": 29.99, "category": "Clothing", "image_url": "https://images.unsplash.com/photo-1521572163474-6864f9cf17ab?w=600", "stock": 300, "rating": 4.4, "review_count": 2890},
    {"name": "Merino Wool Crew Neck Sweater", "description": "100% extra-fine merino wool. Naturally temperature-regulating, soft, and odor-resistant.", "price": 89.99, "category": "Clothing", "image_url": "https://images.unsplash.com/photo-1434389677669-e08b4cac3105?w=600", "stock": 75, "rating": 4.7, "review_count": 678},
    {"name": "Adidas Ultraboost 23", "description": "Our most responsive running shoe ever. BOOST midsole technology returns energy with every step.", "price": 179.99, "category": "Clothing", "image_url": "https://images.unsplash.com/photo-1542291026-7eec264c27ff?w=600", "stock": 55, "rating": 4.8, "review_count": 3421},

    # Books
    {"name": "Atomic Habits — James Clear", "description": "The definitive guide to building good habits and breaking bad ones. #1 New York Times bestseller.", "price": 16.99, "category": "Books", "image_url": "https://images.unsplash.com/photo-1544947950-fa07a98d237f?w=600", "stock": 500, "rating": 4.9, "review_count": 89234},
    {"name": "System Design Interview Vol. 2", "description": "An insider's guide to ace system design interviews at top tech companies. Covers distributed systems fundamentals.", "price": 34.99, "category": "Books", "image_url": "https://images.unsplash.com/photo-1532012197267-da84d127e765?w=600", "stock": 180, "rating": 4.7, "review_count": 5621},
    {"name": "Clean Code — Robert Martin", "description": "A handbook of agile software craftsmanship. Transform messy code into clean, maintainable code.", "price": 37.99, "category": "Books", "image_url": "https://images.unsplash.com/photo-1512820790803-83ca734da794?w=600", "stock": 220, "rating": 4.6, "review_count": 12890},
    {"name": "The Pragmatic Programmer", "description": "20th Anniversary Edition — your journey to mastery. Essential reading for every developer.", "price": 49.99, "category": "Books", "image_url": "https://images.unsplash.com/photo-1551029506-0807df4e2031?w=600", "stock": 95, "rating": 4.8, "review_count": 8765},
    {"name": "Designing Data-Intensive Applications", "description": "Martin Kleppmann's landmark book on the principles behind reliable, scalable, and maintainable systems.", "price": 52.99, "category": "Books", "image_url": "https://images.unsplash.com/photo-1481627834876-b7833e8f5570?w=600", "stock": 140, "rating": 4.9, "review_count": 15432},

    # Home
    {"name": "Dyson V15 Detect Vacuum", "description": "Laser-powered floor detection reveals hidden dust. Automatically optimizes power for the task at hand.", "price": 649.99, "category": "Home", "image_url": "https://images.unsplash.com/photo-1558618666-fcd25c85cd64?w=600", "stock": 20, "rating": 4.7, "review_count": 3210},
    {"name": "Fellow Stagg EKG Kettle", "description": "Variable temperature electric kettle with precision pour spout. The gold standard for pour-over coffee.", "price": 165.00, "category": "Home", "image_url": "https://images.unsplash.com/photo-1544098485-2a2f4c34f457?w=600", "stock": 40, "rating": 4.8, "review_count": 2134},
    {"name": "Philips Hue Starter Kit", "description": "3 smart bulbs + Bridge. 16 million colors, voice control via Alexa/Google, and schedules via app.", "price": 129.99, "category": "Home", "image_url": "https://images.unsplash.com/photo-1524484485831-a92ffc0de03f?w=600", "stock": 60, "rating": 4.5, "review_count": 4521},
    {"name": "Ergotron LX Desk Mount", "description": "Full-motion articulating arm for monitors up to 34\". Near-zero gravity mechanism for effortless adjustment.", "price": 139.99, "category": "Home", "image_url": "https://images.unsplash.com/photo-1593642632559-0c6d3fc62b89?w=600", "stock": 85, "rating": 4.8, "review_count": 6789},
]


def seed():
    db = SessionLocal()
    try:
        existing = db.query(models.Product).count()
        if existing > 0:
            print(f"Database already has {existing} products. Skipping product seed.")
        else:
            for p in PRODUCTS:
                product = models.Product(**p)
                db.add(product)
            db.commit()
            print(f"✅ Seeded {len(PRODUCTS)} products successfully.")

        # Ensure admin user exists
        from app.auth import hash_password
        admin_email = "admin@shopwave.com"
        admin = db.query(models.User).filter(models.User.email == admin_email).first()
        if not admin:
            admin_user = models.User(
                name="Admin",
                email=admin_email,
                hashed_password=hash_password("Admin@123"),
                is_admin=True,
            )
            db.add(admin_user)
            db.commit()
            print("✅ Admin user created: admin@shopwave.com / Admin@123")
        else:
            if not admin.is_admin:
                admin.is_admin = True
                db.commit()
                print("✅ Existing admin@shopwave.com promoted to admin.")
            else:
                print("ℹ️  Admin user already exists.")
    finally:
        db.close()


if __name__ == "__main__":
    seed()

