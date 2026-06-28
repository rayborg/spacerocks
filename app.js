const normalizeText = (value) => String(value || "").toLowerCase().replace(/\s+/g, " ").trim();
const SHOP_DATA_URL = "data/shop.json";
const CONTACT_EMAIL = "spacerocks.club@gmail.com";

const statusLabels = {
  available: "Available",
  inquiry: "Inquiry",
  hold: "On hold",
  sold: "Sold"
};

function setupImageFallbacks(root = document) {
  root.querySelectorAll(".js-safe-image").forEach((image) => {
    if (image.dataset.fallbackReady === "true") return;
    image.dataset.fallbackReady = "true";

    const markMissing = () => {
      image.hidden = true;
      const media = image.closest(".media");
      if (!media) return;
      media.classList.add("is-missing");
      const fallback = media.querySelector(".image-fallback");
      if (fallback && image.dataset.fallbackLabel) {
        fallback.textContent = image.dataset.fallbackLabel;
      }
    };

    image.addEventListener("error", markMissing, { once: true });
    if (image.complete && image.naturalWidth === 0) markMissing();
  });
}

function createElement(tag, className, text) {
  const element = document.createElement(tag);
  if (className) element.className = className;
  if (text !== undefined && text !== null) element.textContent = text;
  return element;
}

function formatWeight(value) {
  if (typeof value !== "number" || !Number.isFinite(value)) return null;
  return `${new Intl.NumberFormat("en-US", { maximumFractionDigits: 3 }).format(value)} g`;
}

function formatPrice(value) {
  if (typeof value !== "number" || !Number.isFinite(value)) return "By inquiry";
  return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(value);
}

function addSpec(list, label, value) {
  if (!value) return;
  const row = createElement("div");
  row.append(createElement("dt", null, label), createElement("dd", null, value));
  list.append(row);
}

function makeBadge(label, extraClass = "") {
  const badge = createElement("span", `badge ${extraClass}`.trim(), label);
  return badge;
}

function buildMetbullLine(item) {
  const metbull = item.metbull || {};
  const parts = [
    metbull.official_name,
    metbull.year,
    metbull.classification,
    metbull.total_known_mass ? `TKW ${metbull.total_known_mass}` : "",
    metbull.bulletin ? `MB ${metbull.bulletin}` : ""
  ].filter(Boolean);
  return parts.join(" | ");
}

function buildInquiryHref(item) {
  const subject = `Inquiry - ${item.title || item.name || "Spacerocks listing"}`;
  const body = [
    "Hello Spacerocks,",
    "",
    `I am interested in ${item.title || item.name || "this listing"}.`,
    "Please send current availability, provenance, price, and shipping details."
  ].join("\n");
  return `mailto:${CONTACT_EMAIL}?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(body)}`;
}

function renderShopImage(item) {
  const image = Array.isArray(item.images) ? item.images[0] : null;
  const media = createElement("div", "media offer-media");
  const fallback = createElement("span", "image-fallback", image ? item.title : "Image pending");

  if (image?.src) {
    const img = document.createElement("img");
    img.className = "js-safe-image";
    img.src = image.src;
    img.alt = image.alt || item.title || "Spacerocks shop listing";
    img.width = 720;
    img.height = 600;
    img.loading = "lazy";
    img.decoding = "async";
    img.dataset.fallbackLabel = image.alt || item.title || "Listing image";
    media.append(img, fallback);
  } else {
    media.classList.add("is-missing");
    media.append(fallback);
  }

  return media;
}

function renderShopCard(item) {
  const status = item.status || "inquiry";
  const card = createElement("article", "offer-card");
  if (item.featured) card.classList.add("featured-offer");
  card.classList.add(`is-${status}`);

  card.append(renderShopImage(item));

  const content = createElement("div", "card-content");
  const badgeRow = createElement("div", "badge-row");
  badgeRow.append(makeBadge(statusLabels[status] || status, `badge-status-${status}`));
  (item.badges || []).slice(0, 4).forEach((badge) => badgeRow.append(makeBadge(badge)));

  const title = createElement("h3", null, item.title || item.name || "Spacerocks listing");
  const description = createElement("p", null, item.description || "Contact Spacerocks for current details and provenance notes.");

  const specs = createElement("dl", "spec-list");
  addSpec(specs, "Mass", formatWeight(item.weight_g));
  addSpec(specs, "Type", item.type || item.classification);
  addSpec(specs, "Price", formatPrice(item.price_usd));
  addSpec(specs, "Status", statusLabels[status] || status);

  const metbullLine = buildMetbullLine(item);
  if (metbullLine) addSpec(specs, "MetBull", metbullLine);

  content.append(badgeRow, title, description, specs);

  if (item.provenance) {
    content.append(createElement("p", "provenance-note", item.provenance));
  }

  const button = createElement("a", item.featured ? "button button-primary" : "button", status === "sold" ? "Ask about similar" : "Request dossier");
  button.href = buildInquiryHref(item);
  content.append(button);
  card.append(content);
  return card;
}

function formatGeneratedAt(value) {
  if (!value) return null;
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return null;
  return new Intl.DateTimeFormat("en-US", {
    dateStyle: "medium",
    timeStyle: "short"
  }).format(date);
}

async function setupShopData() {
  const grid = document.querySelector("[data-shop-grid]");
  const status = document.getElementById("shopRefreshStatus");
  if (!grid || !window.fetch) return;

  try {
    const response = await fetch(SHOP_DATA_URL, { cache: "no-store" });
    if (!response.ok) throw new Error(`Shop data request failed: ${response.status}`);

    const data = await response.json();
    if (!Array.isArray(data.items)) throw new Error("Shop data is missing an items array");

    if (data.items.length) {
      grid.replaceChildren(...data.items.map(renderShopCard));
      setupImageFallbacks(grid);
    } else {
      const empty = createElement("article", "offer-card compact-offer shop-empty");
      const content = createElement("div", "card-content");
      content.append(
        makeBadge("Inventory pending", "badge-status-inquiry"),
        createElement("h3", null, "No generated listings yet"),
        createElement("p", null, "Add an item folder under inventory/shop and the next build will publish it here.")
      );
      empty.append(content);
      grid.replaceChildren(empty);
    }

    const generatedAt = formatGeneratedAt(data.generated_at);
    if (status && generatedAt) {
      status.textContent = `Inventory generated from inventory/shop at ${generatedAt}. GitHub Actions checks for updates about every 10 minutes.`;
    }
  } catch (error) {
    if (status) {
      status.textContent = "Showing fallback shop cards. Generated inventory will appear after data/shop.json is available.";
    }
  }
}

function setupCollectionFilters() {
  const cards = Array.from(document.querySelectorAll("[data-collection-card]"));
  const filterButtons = Array.from(document.querySelectorAll("[data-collection-filter]"));
  const search = document.getElementById("collectionSearch");
  const count = document.getElementById("collectionCount");
  let activeFilter = "all";

  if (!cards.length || !filterButtons.length) return;

  const updateCards = () => {
    const query = normalizeText(search?.value);
    let visibleCount = 0;

    cards.forEach((card) => {
      const tags = normalizeText(card.dataset.tags);
      const haystack = normalizeText(`${card.dataset.name || ""} ${card.textContent}`);
      const matchesFilter = activeFilter === "all" || tags.split(" ").includes(activeFilter);
      const matchesSearch = !query || haystack.includes(query);
      const isVisible = matchesFilter && matchesSearch;

      card.hidden = !isVisible;
      if (isVisible) visibleCount += 1;
    });

    if (count) {
      count.textContent = `${visibleCount} of ${cards.length} collection passports shown`;
    }
  };

  filterButtons.forEach((button) => {
    button.addEventListener("click", () => {
      activeFilter = button.dataset.collectionFilter || "all";
      filterButtons.forEach((item) => {
        const isActive = item === button;
        item.classList.toggle("active", isActive);
        item.setAttribute("aria-pressed", String(isActive));
      });
      updateCards();
    });
  });

  search?.addEventListener("input", updateCards);
  updateCards();
}

function setupFooterYear() {
  const year = document.getElementById("year");
  if (year) year.textContent = String(new Date().getFullYear());
}

setupImageFallbacks();
setupShopData();
setupCollectionFilters();
setupFooterYear();
