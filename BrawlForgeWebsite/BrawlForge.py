from flask import Flask, render_template, request, jsonify, redirect, url_for
import requests
import logging
from collections import defaultdict
import sqlite3

app = Flask(__name__)

# Set up logging for debugging
logging.basicConfig(level=logging.DEBUG)

# SQLite database
DATABASE = "brawlforge.db"

# Initialize the SQLite database
def init_db():
    with sqlite3.connect(DATABASE) as conn:
        cursor = conn.cursor()
        # Table for commanders
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS commanders (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                colors TEXT
            )
        """)
        # Table for submitted cards
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS cards (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                commander_id TEXT NOT NULL,
                name TEXT NOT NULL,
                type TEXT NOT NULL,
                mana_cost TEXT,
                image TEXT,
                FOREIGN KEY (commander_id) REFERENCES commanders (id)
            )
        """)
        conn.commit()

# Initialize the database
init_db()

# Home Page
@app.route("/")
def home():
    return render_template("home.html")


# About Page
@app.route("/about")
def about():
    return render_template("about.html")


@app.route("/decks", methods=["GET"])
def decks():
    # Fetch commanders that are only legal in Brawl
    url = "https://api.scryfall.com/cards/search"
    query = {
        "q": "(type:legendary type:creature) or type:planeswalker legal:brawl"
    }
    commanders = []
    has_more = True

    while has_more:
        response = requests.get(url, params=query)
        if response.status_code == 200:
            data = response.json()
            for card in data["data"]:
                # Only include Brawl-legal cards
                if "brawl" in card.get("legalities", {}) and card["legalities"]["brawl"] == "legal":
                    color_identity = card.get("color_identity", [])
                    colors = "-".join(sorted(color_identity)) if color_identity else "Colorless"
                    image_url = card.get("image_uris", {}).get("normal", "https://via.placeholder.com/150")
                    commanders.append({
                        "name": card["name"],
                        "image": image_url,
                        "slug": card["id"],
                        "colors": colors
                    })

            has_more = data.get("has_more", False)
            if has_more:
                url = data["next_page"]
        else:
            return render_template("decks.html", commanders=[], error="Error fetching commanders.")

    # Filter commanders by selected color
    selected_color = request.args.get("color", "all")
    filtered_commanders = []

    if selected_color != "all":
        # Normalize selected color for comparison
        selected_color_normalized = "-".join(sorted(selected_color.split("-")))
        logging.debug(f"Selected Color (Normalized): {selected_color_normalized}")
        filtered_commanders = [
            commander for commander in commanders
            if commander["colors"] == selected_color_normalized
        ]
    else:
        filtered_commanders = commanders

    # Debug logging for filtered commanders
    logging.debug(f"Filtered Commanders: {len(filtered_commanders)} commanders found")

    return render_template("decks.html", commanders=filtered_commanders, selected_color=selected_color)


@app.route("/commander/<slug>")
def commander_details(slug):
    url = f"https://api.scryfall.com/cards/{slug}"
    response = requests.get(url)

    if response.status_code == 200:
        card = response.json()
        commander_name = card["name"]

        # Fetch submitted cards for this commander from the database
        with sqlite3.connect(DATABASE) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT name, type, mana_cost, image 
                FROM cards WHERE commander_id = ?
            """, (slug,))
            submitted_cards = cursor.fetchall()

        submitted_deck_cards = defaultdict(list)
        for name, card_type, mana_cost, image in submitted_cards:
            card_data = {
                "name": name,
                "mana_cost": mana_cost,
                "image_uris": {"normal": image},  # Wrap image URL in expected structure
            }
            if "creature" in card_type:
                submitted_deck_cards["Creatures"].append(card_data)
            elif "instant" in card_type:
                submitted_deck_cards["Instants"].append(card_data)
            elif "sorcery" in card_type:
                submitted_deck_cards["Sorceries"].append(card_data)
            elif "artifact" in card_type:
                submitted_deck_cards["Artifacts"].append(card_data)
            elif "enchantment" in card_type:
                submitted_deck_cards["Enchantments"].append(card_data)
            elif "land" in card_type:
                submitted_deck_cards["Lands"].append(card_data)

        return render_template(
            "commander.html",
            commander=card,
            submitted_deck_cards=submitted_deck_cards,
        )
    else:
        return render_template("404.html"), 404



@app.route('/submit-deck', methods=['GET', 'POST'])
def submit_deck():
    if request.method == 'POST':
        commander_name = request.form['commander']
        decklist = request.form['decklist']

        # Validate commander name
        response = requests.get(f"https://api.scryfall.com/cards/named?fuzzy={commander_name}")
        if response.status_code == 200:
            commander_data = response.json()
            commander_slug = commander_data.get("id")  # Use Scryfall's unique slug
            commander_colors = "-".join(sorted(commander_data.get("color_identity", [])))
        else:
            # If commander is not found, show an error page
            return render_template("404.html"), 404

        # Add commander to the database if not already present
        with sqlite3.connect(DATABASE) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR IGNORE INTO commanders (id, name, colors) 
                VALUES (?, ?, ?)
            """, (commander_slug, commander_name, commander_colors))
            conn.commit()

        # Parse the decklist and avoid duplicates
        card_names = decklist.splitlines()
        with sqlite3.connect(DATABASE) as conn:
            cursor = conn.cursor()
            for card_name in card_names:
                card_name = card_name.strip()
                if card_name:
                    # Fetch card details from Scryfall
                    response = requests.get(f"https://api.scryfall.com/cards/named?fuzzy={card_name}")
                    if response.status_code == 200:
                        card_data = response.json()
                        card_type = card_data.get("type_line", "").lower()
                        mana_cost = card_data.get("mana_cost", "")
                        image_url = card_data.get("image_uris", {}).get("normal", "https://via.placeholder.com/150")

                        # Check if the card already exists in the database
                        cursor.execute("""
                            SELECT COUNT(*) FROM cards 
                            WHERE commander_id = ? AND name = ?
                        """, (commander_slug, card_data["name"]))
                        exists = cursor.fetchone()[0]

                        if exists == 0:  # Only insert if it doesn't already exist
                            cursor.execute("""
                                INSERT INTO cards (commander_id, name, type, mana_cost, image)
                                VALUES (?, ?, ?, ?, ?)
                            """, (commander_slug, card_data["name"], card_type, mana_cost, image_url))
            conn.commit()

        # Redirect back to home after submission
        return redirect(url_for('home'))

    return render_template('submit_deck.html')



@app.route('/search-commander', methods=['GET'])
def search_commander():
    query = request.args.get('q', '').strip()

    if not query:
        return redirect(url_for('home'))

    # Validate commander name with Scryfall API
    response = requests.get(f"https://api.scryfall.com/cards/named?fuzzy={query}")
    if response.status_code == 200:
        commander_data = response.json()
        commander_slug = commander_data.get("id")  # Get the unique commander ID (slug)
        return redirect(url_for('commander_details', slug=commander_slug))
    else:
        # If commander is not found, show an error
        return render_template("404.html"), 404

@app.route('/autocomplete', methods=['GET'])
def autocomplete():
    query = request.args.get('q', '').strip()

    if not query:
        return jsonify([])  # Return an empty list if query is empty

    # Search for commanders matching the query
    response = requests.get(f"https://api.scryfall.com/cards/search?q={query} (type:legendary or type:planeswalker) legal:brawl")
    if response.status_code == 200:
        data = response.json()
        commanders = [
            {"name": card["name"], "id": card["id"]}
            for card in data.get("data", [])
        ]
        return jsonify(commanders)
    else:
        return jsonify([])

# CLEAN UP
def remove_non_legal_cards_and_duplicates():
    # Connect to the database
    with sqlite3.connect("brawlforge.db") as conn:
        cursor = conn.cursor()

        # Step 1: Remove duplicates
        # Find and delete duplicate cards (same name and commander_id)
        cursor.execute("""
            DELETE FROM cards
            WHERE id NOT IN (
                SELECT MIN(id)
                FROM cards
                GROUP BY commander_id, name
            )
        """)
        print("Duplicate cards have been removed.")

        # Step 2: Remove non-legal cards
        # Fetch all cards in the database
        cursor.execute("SELECT id, name FROM cards")
        all_cards = cursor.fetchall()

        for card_id, card_name in all_cards:
            # Check if the card is legal in Historic Brawl
            response = requests.get(f"https://api.scryfall.com/cards/named?fuzzy={card_name}")
            if response.status_code == 200:
                card_data = response.json()
                legalities = card_data.get("legalities", {})

                # If the card is not legal in Brawl, delete it
                if legalities.get("brawl") != "legal":
                    cursor.execute("DELETE FROM cards WHERE id = ?", (card_id,))

        # Commit the changes
        conn.commit()
        print("Non-legal cards have been removed.")


#USE THE FOLLOWING IF YOU WANT TO CLEAN THE DATABASE OF ALL NON BRAWL CARDS AND DUPLICATES (remove the hashtag)
#remove_non_legal_cards_and_duplicates()

if __name__ == "__main__":
    app.run(debug=True)
