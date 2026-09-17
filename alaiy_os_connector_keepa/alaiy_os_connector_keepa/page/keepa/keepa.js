frappe.pages["keepa"].on_page_load = function (wrapper) {
  const page = frappe.ui.make_app_page({
    parent: wrapper,
    title: "Keepa",
    single_column: true,
  });

  new KeepaDashboardPage(page);
};

function _format_price(value) {
  // Keepa doesn't return a currency code alongside price, and we have no
  // confirmed currency-formatting global available in this codebase to
  // reuse, so this is a plain $-prefixed display, not localized.
  return `$${value.toFixed(2)}`;
}

// One card per real Keepa endpoint. cost is what a normal call actually
// costs (see keepa/token_cost.py) -- shown up front so nobody clicks in
// blind. panel is the id of the detail view rendered when the card opens.
const FEATURES = [
  { id: "product", label: "Product Intelligence", icon: "trending-up", cost: "~5 tokens",
    desc: "Price history, BSR, rating/reviews, offers, product details -- one ASIN." },
  { id: "search_product", label: "Product Search", icon: "search", cost: "10 tokens",
    desc: "Find Amazon products by keyword (up to 20 results)." },
  { id: "product_finder", label: "Product Finder", icon: "filter", cost: "10 + 1/100 ASINs",
    desc: "Attribute/filter search across the whole Keepa database." },
  { id: "deals", label: "Browsing Deals", icon: "percent", cost: "5 / 150 deals",
    desc: "Products with a recent significant price drop." },
  { id: "bestsellers", label: "Best Sellers", icon: "award", cost: "50 tokens",
    desc: "Top ASINs in a category by sales rank." },
  { id: "category", label: "Category Lookup", icon: "folder", cost: "1 token",
    desc: "Look up a category node (and its parent tree) by ID." },
  { id: "search_category", label: "Category Search", icon: "search",
    cost: "1 token", desc: "Find category node IDs by name." },
  { id: "seller", label: "Seller Information", icon: "user", cost: "1 token (+9 storefront)",
    desc: "Look up a marketplace seller by ID." },
  { id: "seller_finder", label: "Seller Finder", icon: "users", cost: "10 + 1/100 sellers",
    desc: "Search sellers by rating, business details, catalogue profile." },
  { id: "top_sellers", label: "Most Rated Sellers", icon: "star", cost: "50 tokens",
    desc: "Top seller IDs by rating count for a marketplace." },
  { id: "lightning_deals", label: "Lightning Deals", icon: "zap", cost: "1 / 500 tokens",
    desc: "A single lightning deal by ASIN, or the full current list." },
  { id: "graph_image", label: "Graph Image", icon: "image", cost: "1 token",
    desc: "Server-rendered PNG price/rank chart for one ASIN." },
  { id: "tracking", label: "Tracking", icon: "bell", cost: "1 token to add, 0 otherwise",
    desc: "Server-side price/rank alerts -- add, list, remove trackings." },
];

class KeepaDashboardPage {
  constructor(page) {
    this.page = page;
    this.$body = $(page.body);
    this.charts = {};
    this.render_home();
  }

  render_home() {
    this.$body.empty();
    this.$body.append(`
      <div class="keepa-dashboard" style="max-width: 1000px;">
        <div class="text-muted" style="margin-bottom: 16px;">
          One card per Keepa endpoint this connector wires up. Each shows its
          real token cost before you click. Test Connection on
          <a href="/app/keepa-connector-settings">Keepa Connector Settings</a>
          is free -- do that first to confirm the key works.
        </div>
        <div class="row" id="keepa-feature-cards"></div>
        <div id="keepa-panel" style="margin-top: 16px;"></div>
      </div>
    `);

    const $cards = this.$body.find("#keepa-feature-cards");
    FEATURES.forEach((f) => {
      $(`
        <div class="col-sm-4" style="margin-bottom: 16px;">
          <div class="frappe-card keepa-feature-card" data-feature="${f.id}"
               style="padding: 14px; cursor: pointer; height: 100%;">
            <div style="font-weight: 600;">${frappe.utils.escape_html(f.label)}</div>
            <div class="text-muted small" style="margin: 4px 0;">${frappe.utils.escape_html(f.desc)}</div>
            <span class="indicator-pill gray">${frappe.utils.escape_html(f.cost)}</span>
          </div>
        </div>
      `).appendTo($cards);
    });

    $cards.find(".keepa-feature-card").on("click", (e) => {
      const featureId = $(e.currentTarget).data("feature");
      this.open_panel(featureId);
    });
  }

  open_panel(featureId) {
    const $panel = this.$body.find("#keepa-panel");
    $panel[0].scrollIntoView({ behavior: "smooth", block: "nearest" });
    const renderer = this[`panel_${featureId}`];
    if (typeof renderer === "function") {
      renderer.call(this, $panel);
    } else {
      $panel.html(`<div class="text-danger">No panel for "${featureId}" yet.</div>`);
    }
  }

  _panel_shell($panel, title, bodyHtml) {
    $panel.html(`
      <div class="frappe-card" style="padding: 16px;">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
          <h5 style="margin: 0;">${frappe.utils.escape_html(title)}</h5>
          <button class="btn btn-xs btn-default" id="keepa-panel-close">Close</button>
        </div>
        ${bodyHtml}
      </div>
    `);
    $panel.find("#keepa-panel-close").on("click", () => $panel.empty());
  }

  _asin_input(placeholder) {
    return `<input type="text" class="form-control keepa-input-asin" placeholder="${placeholder || "e.g. B0F3GWXLTS"}" style="max-width: 300px; display: inline-block;">`;
  }

  _run($panel, method, args, onSuccess) {
    const $result = $panel.find(".keepa-panel-result");
    $result.html(`<div class="text-muted">Calling...</div>`);
    frappe.call({
      method,
      args,
      callback: (r) => onSuccess(r.message || {}, $result),
      error: () => $result.html(`<div class="text-danger">Call failed -- check the Error Log.</div>`),
    });
  }

  // ---- Product Intelligence (the original combined view) ---------------

  panel_product($panel) {
    this._panel_shell($panel, "Product Intelligence", `
      <div class="form-group">
        <div class="input-group" style="max-width: 420px;">
          ${this._asin_input()}
          <span class="input-group-btn">
            <button class="btn btn-primary keepa-load-product">Load (~5 tokens)</button>
          </span>
        </div>
        <button class="btn btn-default btn-xs keepa-load-demo" style="margin-top: 8px;">
          Load Demo Data (0 tokens -- fake sample, checks the UI only)
        </button>
      </div>
      <div class="keepa-product-body" style="display:none; margin-top: 16px;">
        <div class="frappe-card" style="padding: 16px; margin-bottom: 16px; display: flex; gap: 16px;">
          <img class="kt-image" style="width: 100px; height: 100px; object-fit: contain; border: 1px solid var(--border-color); border-radius: 4px;">
          <div>
            <div style="font-weight: 600; font-size: 15px;" class="kt-title"></div>
            <div class="text-muted kt-brand"></div>
            <div class="text-muted kt-ids"></div>
          </div>
        </div>
        <div class="row" style="margin-bottom: 16px;">
          ${this._stat_tile("kt-buybox", "Buy Box Price")}
          ${this._stat_tile("kt-bsr", "Sales Rank (BSR)")}
          ${this._stat_tile("kt-rating", "Rating")}
          ${this._stat_tile("kt-reviews", "Review Count")}
        </div>
        <div class="frappe-card" style="padding: 16px; margin-bottom: 16px;">
          <h6>Buy Box Price History</h6>
          <div class="kt-chart-price"></div>
        </div>
        <div class="frappe-card" style="padding: 16px; margin-bottom: 16px;">
          <h6>BSR History <span class="text-muted small">(lower is better -- axis inverted)</span></h6>
          <div class="kt-chart-bsr"></div>
        </div>
        <div class="frappe-card" style="padding: 16px;">
          <h6>Current Offers</h6>
          <div class="kt-offers-table"></div>
        </div>
      </div>
      <div class="text-danger keepa-product-error" style="display:none; margin-top: 8px;"></div>
    `);

    $panel.find(".keepa-load-product").on("click", () => this._load_product($panel));
    $panel.find(".keepa-input-asin").on("keypress", (e) => {
      if (e.which === 13) this._load_product($panel);
    });
    $panel.find(".keepa-load-demo").on("click", () => this._load_product_demo($panel));
  }

  _stat_tile(cls, label) {
    return `
      <div class="col-sm-3">
        <div class="frappe-card" style="padding: 12px; text-align: center;">
          <div class="text-muted small">${label}</div>
          <div style="font-size: 20px; font-weight: 600;" class="${cls}">--</div>
        </div>
      </div>
    `;
  }

  _load_product($panel) {
    const asin = $panel.find(".keepa-input-asin").val().trim();
    if (!asin) {
      frappe.show_alert({ message: __("Enter an ASIN first"), indicator: "orange" });
      return;
    }
    $panel.find(".keepa-product-body").hide();
    $panel.find(".keepa-product-error").hide();

    Promise.all([
      this._call("alaiy_os_connector_keepa.api.product.get_product_details", { asin }),
      this._call("alaiy_os_connector_keepa.api.product.get_price_history", { asin, price_type: "buy_box" }),
      this._call("alaiy_os_connector_keepa.api.product.get_bsr_history", { asin }),
      this._call("alaiy_os_connector_keepa.api.product.get_review_history", { asin }),
      this._call("alaiy_os_connector_keepa.api.product.get_current_offers", { asin }),
    ])
      .then(([details, price, bsr, reviews, offers]) => {
        $panel.find(".keepa-product-body").show();
        this._render_product($panel, details);
        this._render_stats($panel, price, bsr, reviews);
        this._render_price_chart($panel, price);
        this._render_bsr_chart($panel, bsr);
        this._render_offers($panel, offers);
      })
      .catch((err) => {
        $panel.find(".keepa-product-error").text(err.message || "Call failed -- check the Error Log.").show();
      });
  }

  _load_product_demo($panel) {
    const now = new Date();
    const daysAgo = (n) => new Date(now.getTime() - n * 86400000).toISOString();
    const details = {
      asin: "DEMO000001", found: true,
      title: "Demo Product -- Wireless Noise Cancelling Headphones",
      brand: "DemoBrand", manufacturer: "DemoBrand Inc.", images: [],
      upc_list: ["012345678905"],
    };
    const price = {
      found: true,
      points: [30, 25, 20, 15, 10, 5, 0].map((d, i) => ({ time: daysAgo(d), value: 89.99 - i * 3 + (i % 2 === 0 ? 4 : 0) })),
    };
    const bsr = {
      found: true,
      points: [30, 25, 20, 15, 10, 5, 0].map((d, i) => ({ time: daysAgo(d), value: 4200 - i * 250 })),
    };
    const reviews = {
      found: true,
      rating: { points: [30, 15, 0].map((d) => ({ time: daysAgo(d), value: 4.3 })) },
      reviews: { points: [30, 15, 0].map((d, i) => ({ time: daysAgo(d), value: 1180 + i * 40 })) },
    };
    const offers = {
      found: true,
      offers: [
        { seller_id: "A1DEMO0000001", price: 86.99, shipping: 0, condition: "New", is_fba: true, is_fresh: true },
        { seller_id: "A1DEMO0000002", price: 91.99, shipping: 4.99, condition: "New", is_fba: false, is_fresh: true },
        { seller_id: "A1DEMO0000003", price: 79.99, shipping: 0, condition: "Used - Like New", is_fba: true, is_fresh: false },
      ],
    };
    $panel.find(".keepa-product-error").hide();
    $panel.find(".keepa-product-body").show();
    this._render_product($panel, details);
    this._render_stats($panel, price, bsr, reviews);
    this._render_price_chart($panel, price);
    this._render_bsr_chart($panel, bsr);
    this._render_offers($panel, offers);
    frappe.show_alert({ message: __("Showing demo data -- not real, 0 tokens spent"), indicator: "blue" });
  }

  _call(method, args) {
    return new Promise((resolve, reject) => {
      frappe.call({
        method, args,
        callback: (r) => resolve(r.message || {}),
        error: () => reject(new Error(`${method} failed`)),
      });
    });
  }

  _render_product($panel, details) {
    if (!details.found) {
      $panel.find(".kt-title").text("Not found");
      return;
    }
    $panel.find(".kt-title").text(details.title || "(no title)");
    $panel.find(".kt-brand").text(details.brand || details.manufacturer || "");
    $panel.find(".kt-ids").html(
      `ASIN: ${frappe.utils.escape_html(details.asin)}` +
      (details.upc_list && details.upc_list.length ? ` &middot; UPC: ${details.upc_list[0]}` : ""),
    );
    if (details.images && details.images.length) {
      $panel.find(".kt-image").attr("src", details.images[0]).show();
    } else {
      $panel.find(".kt-image").hide();
    }
  }

  _render_stats($panel, price, bsr, reviews) {
    const lastPrice = price.points && price.points.length ? price.points[price.points.length - 1].value : null;
    const lastBsr = bsr.points && bsr.points.length ? bsr.points[bsr.points.length - 1].value : null;
    const lastRating = reviews.rating && reviews.rating.points.length ? reviews.rating.points[reviews.rating.points.length - 1].value : null;
    const lastReviewCount = reviews.reviews && reviews.reviews.points.length ? reviews.reviews.points[reviews.reviews.points.length - 1].value : null;

    $panel.find(".kt-buybox").text(lastPrice != null ? _format_price(lastPrice) : "no data");
    $panel.find(".kt-bsr").text(lastBsr != null ? `#${lastBsr.toLocaleString()}` : "no data");
    $panel.find(".kt-rating").text(lastRating != null ? `${lastRating.toFixed(1)} / 5` : "no data");
    $panel.find(".kt-reviews").text(lastReviewCount != null ? lastReviewCount.toLocaleString() : "no data");
  }

  _render_price_chart($panel, price) {
    this._destroy("price");
    const $el = $panel.find(".kt-chart-price");
    if (!price.points || !price.points.length) {
      $el.html('<div class="text-muted">No price history yet.</div>');
      return;
    }
    this.charts.price = new frappe.Chart($el[0], {
      data: {
        labels: price.points.map((p) => frappe.datetime.str_to_user(p.time.slice(0, 10))),
        datasets: [{ name: "Buy Box Price", values: price.points.map((p) => p.value) }],
      },
      type: "line", height: 220, colors: ["#5e64ff"],
    });
  }

  _render_bsr_chart($panel, bsr) {
    this._destroy("bsr");
    const $el = $panel.find(".kt-chart-bsr");
    if (!bsr.points || !bsr.points.length) {
      $el.html('<div class="text-muted">No BSR history yet.</div>');
      return;
    }
    this.charts.bsr = new frappe.Chart($el[0], {
      data: {
        labels: bsr.points.map((p) => frappe.datetime.str_to_user(p.time.slice(0, 10))),
        datasets: [{ name: "BSR (inverted, higher = better rank)", values: bsr.points.map((p) => -p.value) }],
      },
      type: "line", height: 220, colors: ["#ff5858"],
    });
  }

  _render_offers($panel, offers) {
    const $t = $panel.find(".kt-offers-table");
    if (!offers.found || !offers.offers || !offers.offers.length) {
      $t.html('<div class="text-muted">No live offers data.</div>');
      return;
    }
    const rows = offers.offers.slice(0, 10).map((o) => {
      const staleBadge = o.is_fresh ? "" : ` <span class="text-muted small">(stale)</span>`;
      return `<tr class="${o.is_fresh ? "" : "text-muted"}">
        <td>${o.seller_id ? frappe.utils.escape_html(o.seller_id) : "--"}</td>
        <td>${o.price != null ? _format_price(o.price) : "--"}</td>
        <td>${o.shipping != null ? _format_price(o.shipping) : (o.shipping === 0 ? "Free" : "--")}</td>
        <td>${frappe.utils.escape_html(o.condition)}</td>
        <td>${o.is_fba ? "FBA" : "FBM"}${staleBadge}</td>
      </tr>`;
    });
    $t.html(`
      <table class="table table-condensed">
        <thead><tr><th>Seller</th><th>Price</th><th>Shipping</th><th>Condition</th><th>Fulfillment</th></tr></thead>
        <tbody>${rows.join("")}</tbody>
      </table>
    `);
  }

  _destroy(key) {
    if (this.charts[key]) {
      try { this.charts[key].destroy(); } catch (e) { /* nothing to tear down */ }
      delete this.charts[key];
    }
  }

  // ---- Product Search ----------------------------------------------------

  panel_search_product($panel) {
    this._panel_shell($panel, "Product Search (10 tokens)", `
      <div class="input-group" style="max-width: 420px;">
        <input type="text" class="form-control keepa-input-term" placeholder="e.g. wireless mouse">
        <span class="input-group-btn"><button class="btn btn-primary keepa-run">Search</button></span>
      </div>
      <div class="keepa-panel-result" style="margin-top: 12px;"></div>
    `);
    $panel.find(".keepa-run").on("click", () => {
      const term = $panel.find(".keepa-input-term").val().trim();
      if (!term) return frappe.show_alert({ message: __("Enter a search term"), indicator: "orange" });
      this._run($panel, "alaiy_os_connector_keepa.api.search.search_products", { keyword: term }, (res, $result) => {
        const asins = res.asins || [];
        $result.html(asins.length
          ? `<ul>${asins.map((a) => `<li>${frappe.utils.escape_html(a)}</li>`).join("")}</ul>`
          : '<div class="text-muted">No results.</div>');
      });
    });
  }

  // ---- Product Finder ------------------------------------------------------

  panel_product_finder($panel) {
    this._panel_shell($panel, "Product Finder (10 + 1/100 ASINs)", `
      <div class="text-muted small" style="margin-bottom: 8px;">
        Raw filter JSON, e.g. <code>{"rootCategory": [172282], "current_AMAZON_lte": 5000}</code>
      </div>
      <textarea class="form-control keepa-input-filter" rows="3" style="max-width: 500px;">{"title": "wireless mouse"}</textarea>
      <button class="btn btn-primary keepa-run" style="margin-top: 8px;">Run</button>
      <div class="keepa-panel-result" style="margin-top: 12px;"></div>
    `);
    $panel.find(".keepa-run").on("click", () => {
      const raw = $panel.find(".keepa-input-filter").val().trim();
      let params;
      try { params = JSON.parse(raw); } catch (e) {
        return frappe.show_alert({ message: __("Invalid JSON"), indicator: "red" });
      }
      this._run($panel, "alaiy_os_connector_keepa.api.product_finder.find_products",
        { filter_params: JSON.stringify(params) }, (res, $result) => {
          $result.html(`
            <div class="text-muted small">${res.total_results || 0} total matches</div>
            <ul>${(res.asins || []).map((a) => `<li>${frappe.utils.escape_html(a)}</li>`).join("")}</ul>
          `);
        });
    });
  }

  // ---- Browsing Deals --------------------------------------------------

  panel_deals($panel) {
    this._panel_shell($panel, "Browsing Deals (5 tokens / 150 deals)", `
      <button class="btn btn-primary keepa-run">Get Recent Deals</button>
      <div class="keepa-panel-result" style="margin-top: 12px;"></div>
    `);
    $panel.find(".keepa-run").on("click", () => {
      this._run($panel, "alaiy_os_connector_keepa.api.deals.get_deals", {}, (res, $result) => {
        const deals = res.deals || [];
        $result.html(deals.length
          ? `<ul>${deals.slice(0, 20).map((d) => `<li>${frappe.utils.escape_html(d.title || d.asin)}</li>`).join("")}</ul>`
          : '<div class="text-muted">No deals found.</div>');
      });
    });
  }

  // ---- Best Sellers -----------------------------------------------------

  panel_bestsellers($panel) {
    this._panel_shell($panel, "Best Sellers (50 tokens)", `
      <div class="input-group" style="max-width: 420px;">
        <input type="text" class="form-control keepa-input-category" placeholder="category node ID, e.g. 281052">
        <span class="input-group-btn"><button class="btn btn-primary keepa-run">Get List</button></span>
      </div>
      <div class="keepa-panel-result" style="margin-top: 12px;"></div>
    `);
    $panel.find(".keepa-run").on("click", () => {
      const categoryId = $panel.find(".keepa-input-category").val().trim();
      if (!categoryId) return frappe.show_alert({ message: __("Enter a category ID"), indicator: "orange" });
      this._run($panel, "alaiy_os_connector_keepa.api.bestsellers.get_category_bestsellers",
        { category_id: categoryId }, (res, $result) => {
          const asins = res.asins || [];
          $result.html(asins.length
            ? `<ul>${asins.slice(0, 20).map((a) => `<li>${frappe.utils.escape_html(a)}</li>`).join("")}</ul>`
            : '<div class="text-muted">No list found for this category.</div>');
        });
    });
  }

  // ---- Category Lookup / Search -----------------------------------------

  panel_category($panel) {
    this._panel_shell($panel, "Category Lookup (1 token)", `
      <div class="input-group" style="max-width: 420px;">
        <input type="text" class="form-control keepa-input-category" placeholder="category node ID, e.g. 281052">
        <span class="input-group-btn"><button class="btn btn-primary keepa-run">Look Up</button></span>
      </div>
      <div class="keepa-panel-result" style="margin-top: 12px;"></div>
    `);
    $panel.find(".keepa-run").on("click", () => {
      const categoryId = $panel.find(".keepa-input-category").val().trim();
      if (!categoryId) return frappe.show_alert({ message: __("Enter a category ID"), indicator: "orange" });
      this._run($panel, "alaiy_os_connector_keepa.api.category.get_category",
        { category_id: categoryId, parents: 1 }, (res, $result) => {
          $result.html(`<pre style="max-height: 300px; overflow: auto;">${frappe.utils.escape_html(JSON.stringify(res, null, 2))}</pre>`);
        });
    });
  }

  panel_search_category($panel) {
    this._panel_shell($panel, "Category Search (1 token)", `
      <div class="input-group" style="max-width: 420px;">
        <input type="text" class="form-control keepa-input-term" placeholder="e.g. camera">
        <span class="input-group-btn"><button class="btn btn-primary keepa-run">Search</button></span>
      </div>
      <div class="keepa-panel-result" style="margin-top: 12px;"></div>
    `);
    $panel.find(".keepa-run").on("click", () => {
      const term = $panel.find(".keepa-input-term").val().trim();
      if (!term) return frappe.show_alert({ message: __("Enter a search term"), indicator: "orange" });
      this._run($panel, "alaiy_os_connector_keepa.api.search.search_categories", { term }, (res, $result) => {
        const entries = Object.entries(res || {});
        $result.html(entries.length
          ? `<ul>${entries.map(([id, c]) => `<li>${frappe.utils.escape_html(id)} -- ${frappe.utils.escape_html(c.name || "")}</li>`).join("")}</ul>`
          : '<div class="text-muted">No matches.</div>');
      });
    });
  }

  // ---- Seller Information / Finder / Most Rated -------------------------

  panel_seller($panel) {
    this._panel_shell($panel, "Seller Information (1 token, +9 for storefront)", `
      <div class="input-group" style="max-width: 420px;">
        <input type="text" class="form-control keepa-input-seller" placeholder="e.g. A2L77EE7U53NWQ">
        <span class="input-group-btn"><button class="btn btn-primary keepa-run">Look Up</button></span>
      </div>
      <div class="keepa-panel-result" style="margin-top: 12px;"></div>
    `);
    $panel.find(".keepa-run").on("click", () => {
      const sellerId = $panel.find(".keepa-input-seller").val().trim();
      if (!sellerId) return frappe.show_alert({ message: __("Enter a seller ID"), indicator: "orange" });
      this._run($panel, "alaiy_os_connector_keepa.api.seller.get_seller", { seller_id: sellerId }, (res, $result) => {
        $result.html(`<pre style="max-height: 300px; overflow: auto;">${frappe.utils.escape_html(JSON.stringify(res, null, 2))}</pre>`);
      });
    });
  }

  panel_seller_finder($panel) {
    this._panel_shell($panel, "Seller Finder (10 + 1/100 sellers)", `
      <div class="text-muted small" style="margin-bottom: 8px;">
        Raw filter JSON, e.g. <code>{"addressCountry": ["cn", "hk"], "activeOnly": true}</code>
      </div>
      <textarea class="form-control keepa-input-filter" rows="3" style="max-width: 500px;">{"activeOnly": true, "currentRatingCount_gte": 1000}</textarea>
      <button class="btn btn-primary keepa-run" style="margin-top: 8px;">Run</button>
      <div class="keepa-panel-result" style="margin-top: 12px;"></div>
    `);
    $panel.find(".keepa-run").on("click", () => {
      const raw = $panel.find(".keepa-input-filter").val().trim();
      let params;
      try { params = JSON.parse(raw); } catch (e) {
        return frappe.show_alert({ message: __("Invalid JSON"), indicator: "red" });
      }
      this._run($panel, "alaiy_os_connector_keepa.api.seller.find_sellers",
        { seller_params: JSON.stringify(params) }, (res, $result) => {
          $result.html(`
            <div class="text-muted small">${res.total_results || 0} total matches</div>
            <ul>${(res.seller_ids || []).map((s) => `<li>${frappe.utils.escape_html(s)}</li>`).join("")}</ul>
          `);
        });
    });
  }

  panel_top_sellers($panel) {
    this._panel_shell($panel, "Most Rated Sellers (50 tokens)", `
      <button class="btn btn-primary keepa-run">Get List</button>
      <div class="keepa-panel-result" style="margin-top: 12px;"></div>
    `);
    $panel.find(".keepa-run").on("click", () => {
      this._run($panel, "alaiy_os_connector_keepa.api.seller.get_top_sellers", {}, (res, $result) => {
        const ids = res.seller_ids || [];
        $result.html(ids.length
          ? `<ul>${ids.slice(0, 20).map((s) => `<li>${frappe.utils.escape_html(s)}</li>`).join("")}</ul>`
          : '<div class="text-muted">No sellers found.</div>');
      });
    });
  }

  // ---- Lightning Deals ---------------------------------------------------

  panel_lightning_deals($panel) {
    this._panel_shell($panel, "Lightning Deals (1 token by ASIN, 500 for the full list)", `
      <div class="input-group" style="max-width: 420px;">
        ${this._asin_input("optional -- leave blank for the full list (500 tokens)")}
        <span class="input-group-btn"><button class="btn btn-primary keepa-run">Get</button></span>
      </div>
      <div class="keepa-panel-result" style="margin-top: 12px;"></div>
    `);
    $panel.find(".keepa-run").on("click", () => {
      const asin = $panel.find(".keepa-input-asin").val().trim();
      if (asin) {
        this._run($panel, "alaiy_os_connector_keepa.api.lightning_deals.get_lightning_deal", { asin }, (res, $result) => {
          $result.html(`<pre style="max-height: 300px; overflow: auto;">${frappe.utils.escape_html(JSON.stringify(res, null, 2))}</pre>`);
        });
      } else {
        frappe.confirm(__("No ASIN given -- this fetches the FULL list for 500 tokens. Continue?"), () => {
          this._run($panel, "alaiy_os_connector_keepa.api.lightning_deals.get_all_lightning_deals", {}, (res, $result) => {
            const deals = res.deals || [];
            $result.html(deals.length
              ? `<ul>${deals.slice(0, 20).map((d) => `<li>${frappe.utils.escape_html(d.title || d.asin)}</li>`).join("")}</ul>`
              : '<div class="text-muted">No lightning deals found.</div>');
          });
        });
      }
    });
  }

  // ---- Graph Image --------------------------------------------------------

  panel_graph_image($panel) {
    this._panel_shell($panel, "Graph Image (1 token)", `
      <div class="input-group" style="max-width: 420px;">
        ${this._asin_input()}
        <span class="input-group-btn"><button class="btn btn-primary keepa-run">Render</button></span>
      </div>
      <div class="keepa-panel-result" style="margin-top: 12px;"></div>
    `);
    $panel.find(".keepa-run").on("click", () => {
      const asin = $panel.find(".keepa-input-asin").val().trim();
      if (!asin) return frappe.show_alert({ message: __("Enter an ASIN first"), indicator: "orange" });
      const url = `/api/method/alaiy_os_connector_keepa.api.graph_image.get_price_history_image?asin=${encodeURIComponent(asin)}`;
      $panel.find(".keepa-panel-result").html(`<img src="${url}" style="max-width: 100%; border: 1px solid var(--border-color);">`);
    });
  }

  // ---- Tracking -----------------------------------------------------------

  panel_tracking($panel) {
    this._panel_shell($panel, "Tracking (1 token to add, 0 otherwise)", `
      <div class="input-group" style="max-width: 420px;">
        ${this._asin_input()}
        <span class="input-group-btn"><button class="btn btn-default keepa-run-list">List Trackings</button></span>
      </div>
      <div class="text-muted small" style="margin: 8px 0;">
        Adding a tracking creates real, ongoing server-side state on your Keepa
        account (reduces your refill rate) -- test carefully, not a throwaway click.
      </div>
      <button class="btn btn-primary btn-sm keepa-run-add">Add Tracking (Buy Box drop alert)</button>
      <div class="keepa-panel-result" style="margin-top: 12px;"></div>
    `);
    $panel.find(".keepa-run-list").on("click", () => {
      this._run($panel, "alaiy_os_connector_keepa.api.tracking.list_trackings", {}, (res, $result) => {
        $result.html(`<pre style="max-height: 300px; overflow: auto;">${frappe.utils.escape_html(JSON.stringify(res, null, 2))}</pre>`);
      });
    });
    $panel.find(".keepa-run-add").on("click", () => {
      const asin = $panel.find(".keepa-input-asin").val().trim();
      if (!asin) return frappe.show_alert({ message: __("Enter an ASIN first"), indicator: "orange" });
      frappe.confirm(
        __("This creates a real, ongoing tracking on your Keepa account for {0}. Continue?", [asin]),
        () => {
          this._run($panel, "alaiy_os_connector_keepa.api.tracking.add_tracking", { asin }, (res, $result) => {
            $result.html(`<pre style="max-height: 300px; overflow: auto;">${frappe.utils.escape_html(JSON.stringify(res, null, 2))}</pre>`);
          });
        },
      );
    });
  }
}
