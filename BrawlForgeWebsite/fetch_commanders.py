import requests

def fetch_historic_brawl_commanders():
    url = "https://api.scryfall.com/cards/search"
    query = {
        "q": "is:historicbrawl (type:legendary or type:planeswalker)"
    }
    all_commanders = []
    has_more = True

    while has_more:
        response = requests.get(url, params=query)
        if response.status_code == 200:
            data = response.json()
            all_commanders.extend(data["data"])
            has_more = data.get("has_more", False)
            if has_more:
                url = data["next_page"]
        else:
            print("Error fetching commanders:", response.status_code)
            break

    # Organize commanders by color identity
    commanders_by_color = {}
    for card in all_commanders:
        colors = "".join(card.get("color_identity", [])) or "Colorless"
        if colors not in commanders_by_color:
            commanders_by_color[colors] = []
        commanders_by_color[colors].append({
            "name": card["name"],
            "image": card["image_uris"]["normal"],
            "slug": card["id"],  # Use the card's unique ID as the slug
            "colors": colors
        })

    return commanders_by_color

# Fetch and print the results (use this to generate your dataset)
if __name__ == "__main__":
    commanders = fetch_historic_brawl_commanders()
    print(commanders)
