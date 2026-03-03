import os
import sys
from pathlib import Path

from book_lamp.app import app, get_storage

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

# Force TEST_MODE before importing app
os.environ["TEST_MODE"] = "1"
os.environ["SECRET_KEY"] = "lhci-secret-key"
os.environ["GOOGLE_CLIENT_ID"] = "dummy-id"
os.environ["GOOGLE_CLIENT_SECRET"] = "dummy-secret"


def seed_data():
    with app.app_context():
        storage = get_storage()
        storage.set_authorised(True)

        # Add some sample data for LHCI to render
        if not storage.get_all_books():
            b1 = storage.add_book(
                isbn13="9780140449136",
                title="The Odyssey",
                author="Homer",
                publication_year=1946,
                publisher="Penguin Classics",
                description="The epic journey of Odysseus.",
            )
            b2 = storage.add_book(
                isbn13="9780141439518",
                title="Pride and Prejudice",
                author="Jane Austen",
                publication_year=1813,
                publisher="T. Egerton",
                description="A classic novel of manners.",
            )

            storage.add_reading_record(
                book_id=b1["id"],
                status="Completed",
                start_date="2024-01-01",
                end_date="2024-01-10",
                rating=5,
            )
            storage.add_reading_record(
                book_id=b2["id"], status="In Progress", start_date="2024-02-01"
            )

            storage.add_to_reading_list(b2["id"])


if __name__ == "__main__":
    seed_data()
    print("Seeded LHCI server data.")
    # Run mirroring the ci.yml setup but with a fixed port
    app.run(host="127.0.0.1", port=5000)
