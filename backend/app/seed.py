"""
Seed script — populates the database with a diverse product catalog.
Usage: python -m app.seed
       python -m app.seed --force   (clears existing products first)
"""
import sys
from app.database import SessionLocal, engine
from app import models

models.Base.metadata.create_all(bind=engine)

# ── 20 Diverse Products: Budget · Mid-Range · Premium ──────────────────────
PRODUCTS = [

    # ── Electronics ────────────────────────────────────────────────────────
    # Budget
    {
        "name": "Anker 65W GaN Charger",
        "description": "Compact 3-port GaN charger (USB-C×2 + USB-A) with PowerIQ 3.0. Charges a MacBook Pro at full speed in a palm-sized form factor.",
        "price": 35.99,
        "category": "Electronics",
        "image_url": "https://images.unsplash.com/photo-1558618666-fcd25c85cd64?w=600",
        "stock": 200,
        "rating": 4.7,
        "review_count": 3210,
    },
    # Mid-Range
    {
        "name": "Logitech MX Master 3S Mouse",
        "description": "Advanced wireless mouse with ultra-fast MagSpeed electromagnetic scrolling and 8K DPI optical tracking on any surface, including glass.",
        "price": 99.99,
        "category": "Electronics",
        "image_url": "https://images.unsplash.com/photo-1527864550417-7fd91fc51a46?w=600",
        "stock": 120,
        "rating": 4.9,
        "review_count": 1876,
    },
    # Mid-Range
    {
        "name": "Apple AirPods Pro (2nd Gen)",
        "description": "Active Noise Cancellation, Adaptive Transparency, and Personalized Spatial Audio with dynamic head tracking. MagSafe USB-C case included.",
        "price": 199.99,
        "category": "Electronics",
        "image_url": "https://images.unsplash.com/photo-1572635196237-14b3f281503f?w=600",
        "stock": 80,
        "rating": 4.7,
        "review_count": 5621,
    },
    # Premium
    {
        "name": "Sony WH-1000XM5 Headphones",
        "description": "Industry-leading noise canceling with 8 microphones, 30-hour battery life, and crystal-clear call quality. Foldable for travel.",
        "price": 279.99,
        "category": "Electronics",
        "image_url": "https://images.unsplash.com/photo-1505740420928-5e560c06d30e?w=600",
        "stock": 45,
        "rating": 4.8,
        "review_count": 2341,
    },
    # Premium
    {
        "name": "Samsung 27\" 4K IPS Monitor",
        "description": "Ultra HD 4K IPS panel with HDR400, 99% sRGB color accuracy, 60Hz refresh, and USB-C one-cable connectivity. Perfect for creators and developers.",
        "price": 449.99,
        "category": "Electronics",
        "image_url": "https://images.unsplash.com/photo-1527443224154-c4a3942d3acf?w=600",
        "stock": 30,
        "rating": 4.6,
        "review_count": 892,
    },

    # ── Books ───────────────────────────────────────────────────────────────
    # Budget
    {
        "name": "Atomic Habits — James Clear",
        "description": "The definitive guide to building good habits and breaking bad ones. Tiny changes, remarkable results. #1 NYT bestseller with 10M+ copies sold.",
        "price": 16.99,
        "category": "Books",
        "image_url": "https://images.unsplash.com/photo-1544947950-fa07a98d237f?w=600",
        "stock": 500,
        "rating": 4.9,
        "review_count": 89234,
    },
    # Mid-Range
    {
        "name": "Clean Code — Robert C. Martin",
        "description": "A handbook of agile software craftsmanship. Transform messy legacy code into clean, maintainable, and testable code. Essential for every developer.",
        "price": 37.99,
        "category": "Books",
        "image_url": "https://images.unsplash.com/photo-1512820790803-83ca734da794?w=600",
        "stock": 220,
        "rating": 4.6,
        "review_count": 12890,
    },
    # Premium
    {
        "name": "Designing Data-Intensive Applications",
        "description": "Martin Kleppmann's landmark book on the principles behind reliable, scalable, and maintainable systems. The definitive guide to modern backend architecture.",
        "price": 52.99,
        "category": "Books",
        "image_url": "https://images.unsplash.com/photo-1481627834876-b7833e8f5570?w=600",
        "stock": 140,
        "rating": 4.9,
        "review_count": 15432,
    },

    # ── Clothing ────────────────────────────────────────────────────────────
    # Budget
    {
        "name": "Nike Dri-FIT Training Tee",
        "description": "Lightweight sweat-wicking fabric keeps you dry during intense workouts. Regular fit allows unrestricted movement for training and everyday wear.",
        "price": 29.99,
        "category": "Clothing",
        "image_url": "https://images.unsplash.com/photo-1521572163474-6864f9cf17ab?w=600",
        "stock": 300,
        "rating": 4.4,
        "review_count": 2890,
    },
    # Mid-Range
    {
        "name": "Levi's 511 Slim Jeans",
        "description": "The iconic slim fit in sustainable stretch denim. Sits below the waist, slim through the hip and thigh with a narrow leg opening.",
        "price": 69.99,
        "category": "Clothing",
        "image_url": "https://images.unsplash.com/photo-1542272604-787c3835535d?w=600",
        "stock": 150,
        "rating": 4.5,
        "review_count": 4567,
    },
    # Mid-Range
    {
        "name": "Merino Wool Crew Neck Sweater",
        "description": "100% extra-fine merino wool — naturally temperature-regulating, machine washable, and odor-resistant. Versatile for work and weekend.",
        "price": 89.99,
        "category": "Clothing",
        "image_url": "https://images.unsplash.com/photo-1434389677669-e08b4cac3105?w=600",
        "stock": 75,
        "rating": 4.7,
        "review_count": 678,
    },
    # Premium
    {
        "name": "Adidas Ultraboost 23 Sneakers",
        "description": "Our most responsive running shoe. Continental™ rubber outsole, BOOST™ midsole returns energy with every footstrike, Primeknit+ upper for a sock-like fit.",
        "price": 189.99,
        "category": "Clothing",
        "image_url": "https://images.unsplash.com/photo-1542291026-7eec264c27ff?w=600",
        "stock": 55,
        "rating": 4.8,
        "review_count": 3421,
    },

    # ── Home & Living ───────────────────────────────────────────────────────
    # Budget
    {
        "name": "Philips Hue White Smart Bulb (4-Pack)",
        "description": "Warm-to-cool white smart LED bulbs, voice-controlled via Alexa and Google Home. Set schedules, routines, and fade timers from your phone.",
        "price": 49.99,
        "category": "Home",
        "image_url": "https://images.unsplash.com/photo-1524484485831-a92ffc0de03f?w=600",
        "stock": 180,
        "rating": 4.5,
        "review_count": 4521,
    },
    # Mid-Range
    {
        "name": "Fellow Stagg EKG Electric Kettle",
        "description": "Variable temperature (135–212°F) kettle with a precision pour spout and hold temperature mode. The gold standard for pour-over coffee and loose-leaf tea.",
        "price": 165.00,
        "category": "Home",
        "image_url": "https://images.unsplash.com/photo-1544098485-2a2f4c34f457?w=600",
        "stock": 40,
        "rating": 4.8,
        "review_count": 2134,
    },
    # Premium
    {
        "name": "Dyson V15 Detect Cordless Vacuum",
        "description": "Laser-powered floor-type detection automatically reveals and counts hidden dust particles. 60-min runtime, HEPA filtration, and whole-machine filtration.",
        "price": 699.99,
        "category": "Home",
        "image_url": "https://images.unsplash.com/photo-1558618666-fcd25c85cd64?w=600",
        "stock": 20,
        "rating": 4.7,
        "review_count": 3210,
    },

    # ── Sports & Fitness ────────────────────────────────────────────────────
    # Budget
    {
        "name": "Resistance Bands Set (5-Pack)",
        "description": "Five graduated resistance levels (10–50 lbs) with door anchor, handles, and ankle straps. Perfect for home workouts, physical therapy, and travel gym.",
        "price": 24.99,
        "category": "Sports",
        "image_url": "https://images.unsplash.com/photo-1517836357463-d25dfeac3438?w=600",
        "stock": 350,
        "rating": 4.5,
        "review_count": 8920,
    },
    # Mid-Range
    {
        "name": "Garmin Forerunner 255 GPS Watch",
        "description": "Advanced GPS running watch with heart rate monitoring, sleep tracking, race predictor, and up to 14 days of battery life. Lightweight at just 49g.",
        "price": 249.99,
        "category": "Sports",
        "image_url": "https://images.unsplash.com/photo-1523275335684-37898b6baf30?w=600",
        "stock": 35,
        "rating": 4.7,
        "review_count": 1563,
    },

    # ── Beauty & Personal Care ───────────────────────────────────────────────
    # Budget
    {
        "name": "CeraVe Daily Moisturizing Lotion",
        "description": "Lightweight, non-greasy moisturizer with hyaluronic acid and 3 essential ceramides. Restores the protective skin barrier. Dermatologist-developed.",
        "price": 14.99,
        "category": "Beauty",
        "image_url": "https://images.unsplash.com/photo-1556228720-195a672e8a03?w=600",
        "stock": 400,
        "rating": 4.8,
        "review_count": 42310,
    },
    # Premium
    {
        "name": "Dyson Airwrap Multi-Styler",
        "description": "Styles, waves, curls, and dries without extreme heat. Coanda effect wraps hair around the barrel. Comes with 6 attachments for all hair types.",
        "price": 599.99,
        "category": "Beauty",
        "image_url": "https://images.unsplash.com/photo-1522338242992-e1a54906a8da?w=600",
        "stock": 15,
        "rating": 4.6,
        "review_count": 7890,
    },

    # ── Kitchen & Dining ────────────────────────────────────────────────────
    # Mid-Range
    {
        "name": "Instant Pot Duo 7-in-1 (6 Qt)",
        "description": "Pressure cooker, slow cooker, rice cooker, steamer, sauté pan, yogurt maker, and food warmer in one. Cooks up to 70% faster than traditional methods.",
        "price": 89.95,
        "category": "Kitchen",
        "image_url": "https://images.unsplash.com/photo-1585515320310-259814833e62?w=600",
        "stock": 95,
        "rating": 4.8,
        "review_count": 76540,
    },
]


def seed(force: bool = False):
    db = SessionLocal()
    try:
        existing = db.query(models.Product).count()
        if existing > 0 and not force:
            print(f"ℹ️  Database already has {existing} products. Use --force to re-seed.")
        else:
            if force and existing > 0:
                # Clear FK-dependent tables first to avoid constraint violations
                if hasattr(models, "CartItem"):
                    db.query(models.CartItem).delete()
                if hasattr(models, "OrderItem"):
                    db.query(models.OrderItem).delete()
                db.flush()
                db.query(models.Product).delete()
                db.commit()
                print(f"🗑️  Cleared {existing} existing products (and dependent cart/order items).")

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
    force_flag = "--force" in sys.argv
    seed(force=force_flag)
