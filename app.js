const normalizeText = (value) => String(value || "").toLowerCase().replace(/\s+/g, " ").trim();
const SHOP_DATA_URL = "data/shop.json";
const SECTION_TITLES = {
  home: "Spacerocks | Meteorite Shop, Collection, and Adventures",
  shop: "Shop | Spacerocks",
  collection: "Personal Collection | Spacerocks",
  adventures: "Meteorite Adventures | Spacerocks",
  trust: "Trust | Spacerocks",
  contact: "Contact | Spacerocks"
};

const statusLabels = {
  available: "Available",
  "coming-soon": "Coming soon",
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
  if (typeof value !== "number" || !Number.isFinite(value)) return "Price pending";
  return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(value);
}

function getCheckoutUrl(item) {
  const url = String(item.checkout_url || "").trim();
  return /^https?:\/\//i.test(url) ? url : "";
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

function countText(count, singular, plural = `${singular}s`) {
  const value = Number(count) || 0;
  return `${value} ${value === 1 ? singular : plural}`;
}

function headingWithCount(tag, label, count) {
  const heading = createElement(tag);
  heading.append(document.createTextNode(label || "Unclassified"), createElement("span", null, String(Number(count) || 0)));
  return heading;
}

function validHttpUrl(value) {
  const url = String(value || "").trim();
  return /^https?:\/\//i.test(url) ? url : "";
}

function focusAndScrollToListing(listingId) {
  requestAnimationFrame(() => {
    const card = document.getElementById(listingId);
    if (!card) return;
    const behavior = window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth";
    card.scrollIntoView({ block: "start", behavior });
    card.focus({ preventScroll: true });
  });
}

function renderTaxonomyName(entry) {
  const item = createElement("li");
  const label = entry.name || "Unnamed meteorite";
  const sourceUrl = validHttpUrl(entry.source_url);
  const listingTitles = (entry.listings || [])
    .map((listing) => listing.title)
    .filter(Boolean);
  const nameNode = sourceUrl ? createElement("a", null, label) : createElement("strong", null, label);

  if (sourceUrl) {
    nameNode.href = sourceUrl;
    nameNode.target = "_blank";
    nameNode.rel = "noopener noreferrer";
  }

  item.append(nameNode, createElement("span", null, countText(entry.count, "listing")));
  if (listingTitles.length) {
    item.append(createElement("small", null, listingTitles.join(" / ")));
  }
  return item;
}

function renderTaxonomySubtype(subtype) {
  const section = createElement("div", "taxonomy-subtype");
  const names = createElement("ul", "taxonomy-names");
  (subtype.names || []).forEach((name) => names.append(renderTaxonomyName(name)));
  section.append(headingWithCount("h5", subtype.name, subtype.count), names);
  return section;
}

function renderTaxonomyType(type) {
  const section = createElement("div", "taxonomy-type");
  section.append(headingWithCount("h4", type.name, type.count));
  (type.subtypes || []).forEach((subtype) => section.append(renderTaxonomySubtype(subtype)));
  return section;
}

function renderTaxonomyClass(group) {
  const article = createElement("article", "taxonomy-class");
  const heading = createElement("div", "taxonomy-class-heading");
  const titleWrap = createElement("div");
  titleWrap.append(createElement("p", "eyebrow", "Class"), headingWithCount("h3", group.name, group.count));
  heading.append(titleWrap, createElement("p", null, `${countText((group.types || []).length, "type")} represented in this class.`));
  article.append(heading);
  (group.types || []).forEach((type) => article.append(renderTaxonomyType(type)));
  return article;
}

function renderTaxonomyIndex(root, taxonomy) {
  const classes = Array.isArray(taxonomy?.classes) ? taxonomy.classes : [];
  if (!classes.length) {
    const empty = createElement("article", "taxonomy-class");
    const heading = createElement("div", "taxonomy-class-heading");
    const titleWrap = createElement("div");
    titleWrap.append(createElement("p", "eyebrow", "Class index"), createElement("h3", null, "Taxonomy pending"));
    heading.append(titleWrap, createElement("p", null, "Add classified inventory and rerun the shop build to publish the Meteoritical Bulletin index."));
    empty.append(heading);
    root.replaceChildren(empty);
    return;
  }

  const source = createElement("p", "taxonomy-source", taxonomy.source || "Meteoritical Bulletin classifications drive this grouping.");
  root.replaceChildren(source, ...classes.map(renderTaxonomyClass));
}

function formatDateOnly(value) {
  if (!value) return null;
  const date = new Date(`${value}T00:00:00Z`);
  if (Number.isNaN(date.getTime())) return null;
  return new Intl.DateTimeFormat("en-US", { dateStyle: "medium", timeZone: "UTC" }).format(date);
}

function renderHighlightItem(entry, item) {
  const listItem = createElement("li");
  const article = createElement("article", "recent-shop-item");
  const main = createElement("div", "recent-shop-item-main");
  const badges = createElement("div", "badge-row");

  (entry.recency_labels || []).forEach((label) => badges.append(makeBadge(label, "badge-new")));
  (entry.reasons || []).forEach((reason) => badges.append(makeBadge(reason.label, "badge-highlight")));

  const title = createElement("h3", null, item.title || item.name || "Meteorite listing");
  const description = createElement("p", null, item.description || "Listing details are being prepared.");
  main.append(badges, title, description);

  const facts = createElement("dl", "recent-shop-facts");
  addSpec(facts, "Listed", formatDateOnly(entry.listed_at));
  addSpec(facts, "Found", formatDateOnly(entry.found_at));
  addSpec(facts, "Class", item.classification || item.taxonomy?.subtype);
  addSpec(facts, "Mass", formatWeight(item.weight_g));
  if (typeof entry.metrics?.price_per_gram_usd === "number") {
    addSpec(facts, "Price / g", `$${entry.metrics.price_per_gram_usd.toFixed(2)}`);
  }

  const actions = createElement("div", "recent-shop-actions");
  const link = createElement("a", "button", "View listing");
  const listingTarget = `listing-${item.slug}`;
  link.href = `#${listingTarget}`;
  link.dataset.listingTarget = listingTarget;
  actions.append(link);

  if ((entry.reasons || []).length) {
    const evidence = createElement("ul", "highlight-evidence");
    entry.reasons.forEach((reason) => evidence.append(createElement("li", null, reason.evidence)));
    main.append(evidence);
  }

  article.append(main, facts, actions);
  listItem.append(article);
  return listItem;
}

function renderShopHighlights(root, highlights, items) {
  const entries = Array.isArray(highlights?.items) ? highlights.items : [];
  const list = root.querySelector("[data-shop-highlight-list]");
  const count = root.querySelector("[data-shop-highlight-count]");
  const note = root.querySelector("[data-shop-highlight-note]");
  if (!entries.length || !list) {
    root.hidden = true;
    return;
  }

  const itemsBySlug = new Map(items.map((item) => [item.slug, item]));
  const rendered = entries
    .map((entry) => {
      const item = itemsBySlug.get(entry.slug);
      return item ? renderHighlightItem(entry, item) : null;
    })
    .filter(Boolean);

  if (!rendered.length) {
    root.hidden = true;
    return;
  }

  root.hidden = false;
  list.replaceChildren(...rendered);
  if (count) count.textContent = countText(rendered.length, "latest listing");
  if (note && Array.isArray(highlights.notes)) note.textContent = highlights.notes.join(" ");
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
  const status = item.status || "available";
  const checkoutUrl = getCheckoutUrl(item);
  const card = createElement("article", "offer-card");
  if (item.slug) card.id = `listing-${item.slug}`;
  card.tabIndex = -1;
  if (item.featured) card.classList.add("featured-offer");
  card.classList.add(`is-${status}`);

  card.append(renderShopImage(item));

  const content = createElement("div", "card-content");
  const badgeRow = createElement("div", "badge-row");
  badgeRow.append(makeBadge(statusLabels[status] || status, `badge-status-${status}`));
  (item.badges || []).slice(0, 4).forEach((badge) => badgeRow.append(makeBadge(badge)));

  const title = createElement("h3", null, item.title || item.name || "Spacerocks listing");
  const description = createElement("p", null, item.description || "Details and provenance notes are being prepared.");

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

  if (checkoutUrl && status === "available") {
    const action = createElement("a", "button button-primary", item.checkout_label || "Buy now");
    action.href = checkoutUrl;
    action.target = "_blank";
    action.rel = "noopener noreferrer";
    content.append(action);
  }

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
  const taxonomy = document.querySelector("[data-shop-taxonomy]");
  const highlights = document.querySelector("[data-shop-highlights]");
  const status = document.getElementById("shopRefreshStatus");
  if (!grid || !window.fetch) return;

  try {
    const response = await fetch(SHOP_DATA_URL, { cache: "no-store" });
    if (!response.ok) throw new Error(`Shop data request failed: ${response.status}`);

    const data = await response.json();
    if (!Array.isArray(data.items)) throw new Error("Shop data is missing an items array");

    if (taxonomy) renderTaxonomyIndex(taxonomy, data.taxonomy);
    if (highlights) renderShopHighlights(highlights, data.highlights, data.items);

    if (data.items.length) {
      grid.replaceChildren(...data.items.map(renderShopCard));
      setupImageFallbacks(grid);
      try {
        const listingId = decodeURIComponent(window.location.hash.replace(/^#/, ""));
        if (listingId.startsWith("listing-")) focusAndScrollToListing(listingId);
      } catch {
        // Ignore malformed hashes; section routing will show the default view.
      }
    } else {
      const empty = createElement("article", "offer-card compact-offer shop-empty");
      const content = createElement("div", "card-content");
      content.append(
        makeBadge("Inventory pending", "badge-status-coming-soon"),
        createElement("h3", null, "No generated listings yet"),
        createElement("p", null, "Add an item folder under inventory/shop and the next build will publish it here.")
      );
      empty.append(content);
      grid.replaceChildren(empty);
    }

    const generatedAt = formatGeneratedAt(data.generated_at);
    if (status && generatedAt) {
      const metbullCount = Number(data.taxonomy?.metbull_item_count) || 0;
      status.textContent = `Inventory taxonomy generated from inventory/shop at ${generatedAt}. ${countText(metbullCount, "listing")} rooted in Meteoritical Bulletin matches. GitHub Actions checks for updates about every 10 minutes.`;
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

function setupSectionTabs() {
  const sections = Array.from(document.querySelectorAll("[data-site-section]"));
  const sectionIds = new Set(sections.map((section) => section.id));
  const hero = document.querySelector(".hero");
  const brandLink = document.querySelector(".brand[href^='#']");
  const navLinks = Array.from(document.querySelectorAll(".nav-links a[href^='#']"));

  if (!sections.length || !sectionIds.has("home")) return;

  document.body.classList.add("tabs-enabled");
  const scrollBehavior = window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth";

  const decodeSectionId = (value) => {
    try {
      return decodeURIComponent(String(value || "").replace(/^#/, ""));
    } catch {
      return "";
    }
  };

  const sectionFromHash = () => {
    const id = decodeSectionId(window.location.hash);
    if (id.startsWith("listing-")) return "shop";
    return sectionIds.has(id) ? id : "home";
  };

  const listingFromHash = () => {
    const id = decodeSectionId(window.location.hash);
    return id.startsWith("listing-") ? id : "";
  };

  const setActiveNav = (activeId) => {
    brandLink?.classList.toggle("active", activeId === "home");
    navLinks.forEach((link) => {
      const target = link.getAttribute("href")?.replace(/^#/, "");
      const isActive = target === activeId;
      link.classList.toggle("active", isActive);
      if (isActive) {
        link.setAttribute("aria-current", "page");
      } else {
        link.removeAttribute("aria-current");
      }
    });
  };

  const showSection = (activeId, { scroll = false } = {}) => {
    sections.forEach((section) => {
      const isActive = section.id === activeId;
      section.hidden = !isActive;
      section.setAttribute("aria-hidden", String(!isActive));
    });

    if (hero) hero.hidden = activeId !== "home";
    document.body.dataset.activeSection = activeId;
    document.title = SECTION_TITLES[activeId] || SECTION_TITLES.home;
    setActiveNav(activeId);

    if (scroll) {
      if (activeId === "home") {
        window.scrollTo({ top: 0, behavior: scrollBehavior });
      } else {
        document.getElementById("main")?.scrollIntoView({ block: "start", behavior: scrollBehavior });
      }
    }
  };

  const showCurrentLocation = ({ scroll = false } = {}) => {
    const listingId = listingFromHash();
    showSection(sectionFromHash(), { scroll: scroll && !listingId });
    if (listingId && scroll) focusAndScrollToListing(listingId);
  };

  document.addEventListener("click", (event) => {
    if (!(event.target instanceof Element)) return;
    const link = event.target.closest("a[href^='#']");
    if (!link) return;

    const listingTarget = link.dataset.listingTarget;
    if (listingTarget) {
      event.preventDefault();
      if (window.location.hash !== `#${listingTarget}`) {
        history.pushState(null, "", `#${listingTarget}`);
      }
      showSection("shop");
      focusAndScrollToListing(listingTarget);
      return;
    }

    const target = decodeSectionId(link.getAttribute("href"));
    if (!sectionIds.has(target)) return;

    event.preventDefault();
    if (window.location.hash !== `#${target}`) {
      history.pushState(null, "", `#${target}`);
    }
    showSection(target, { scroll: true });
  });

  window.addEventListener("hashchange", () => showCurrentLocation({ scroll: true }));
  window.addEventListener("popstate", () => showCurrentLocation({ scroll: true }));
  showCurrentLocation({ scroll: Boolean(listingFromHash()) });
}

setupImageFallbacks();
setupSectionTabs();
setupShopData();
setupCollectionFilters();
setupFooterYear();
