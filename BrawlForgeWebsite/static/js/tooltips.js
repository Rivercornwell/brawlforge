document.addEventListener("DOMContentLoaded", () => {
    const cards = document.querySelectorAll(".card-tooltip");

    cards.forEach(card => {
        card.addEventListener("mouseover", async () => {
            const cardName = card.getAttribute("data-card");
            if (!cardName) return;

            // Fetch card data from Scryfall API
            const response = await fetch(`https://api.scryfall.com/cards/named?fuzzy=${encodeURIComponent(cardName)}`);
            if (response.ok) {
                const cardData = await response.json();
                const tooltip = document.createElement("div");
                tooltip.className = "tooltip";
                tooltip.innerHTML = `
                    <img src="${cardData.image_uris.normal}" alt="${cardData.name}" style="max-width: 200px;">
                    <p><strong>${cardData.name}</strong></p>
                    <p>${cardData.type_line}</p>
                `;
                card.appendChild(tooltip);
            }
        });

        card.addEventListener("mouseout", () => {
            const tooltip = card.querySelector(".tooltip");
            if (tooltip) {
                tooltip.remove();
            }
        });
    });
});
