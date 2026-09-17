frappe.pages["keepa"].on_page_load = function (wrapper) {
  const page = frappe.ui.make_app_page({
    parent: wrapper,
    title: "Keepa Test",
    single_column: true,
  });

  new KeepaTestPage(page);
};

function _format_price(value) {
  // Keepa doesn't return a currency code alongside price, and we have no
  // confirmed currency-formatting global available in this codebase to
  // reuse, so this is a plain $-prefixed display, not localized.
  return `$${value.toFixed(2)}`;
}

class KeepaTestPage {
  constructor(page) {
    this.page = page;
    this.$body = $(page.body);
    this.charts = {};
    this.render();
  }

  render() {
    this.$body.append(`
      <div class="keepa-test-page" style="max-width: 960px;">
        <div class="text-muted" style="margin-bottom: 12px;">
          Free/1-token methods only (issue #297's 7 whitelisted methods + product
          details). Test Connection on
          <a href="/app/keepa-connector-settings">Keepa Connector Settings</a>
          is free -- do that first.
        </div>

        <div class="form-group" style="max-width: 320px;">
          <label>ASIN</label>
          <div class="input-group">
            <input type="text" class="form-control" id="keepa-test-asin" placeholder="e.g. B0F3GWXLTS">
            <span class="input-group-btn">
              <button class="btn btn-primary" id="keepa-test-load">Load (~5 tokens)</button>
            </span>
          </div>
        </div>
        <button class="btn btn-default btn-xs" id="keepa-test-demo" style="margin-bottom: 12px;">
          Load Demo Data (0 tokens -- fake sample, checks the UI only)
        </button>

        <div id="keepa-test-loading" class="text-muted" style="display:none;">Loading (1 token per method, ~6 tokens total)...</div>
        <div id="keepa-test-error" class="text-danger" style="display:none;"></div>

        <div id="keepa-test-body" style="display:none;">

          <div class="frappe-card" style="padding: 16px; margin-bottom: 16px; display: flex; gap: 16px;">
            <img id="kt-image" style="width: 100px; height: 100px; object-fit: contain; border: 1px solid var(--border-color); border-radius: 4px;">
            <div>
              <div style="font-weight: 600; font-size: 15px;" id="kt-title"></div>
              <div class="text-muted" id="kt-brand"></div>
              <div class="text-muted" id="kt-ids"></div>
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
            <div id="kt-chart-price"></div>
          </div>

          <div class="frappe-card" style="padding: 16px; margin-bottom: 16px;">
            <h6>BSR History <span class="text-muted small">(lower is better -- axis inverted)</span></h6>
            <div id="kt-chart-bsr"></div>
          </div>

          <div class="frappe-card" style="padding: 16px;">
            <h6>Current Offers</h6>
            <div id="kt-offers-table"></div>
          </div>

        </div>
      </div>
    `);

    this.$body.find("#keepa-test-load").on("click", () => this.load());
    this.$body.find("#keepa-test-demo").on("click", () => this.load_demo());
    this.$body.find("#keepa-test-asin").on("keypress", (e) => {
      if (e.which === 13) this.load();
    });
  }

  load_demo() {
    // Entirely client-side, shaped exactly like the real whitelisted
    // responses -- zero backend calls, zero tokens, ever. Only use to
    // check the page itself renders correctly before spending anything.
    const now = new Date();
    const daysAgo = (n) => new Date(now.getTime() - n * 86400000).toISOString();
    const details = {
      asin: "DEMO000001",
      found: true,
      title: "Demo Product -- Wireless Noise Cancelling Headphones",
      brand: "DemoBrand",
      manufacturer: "DemoBrand Inc.",
      images: [],
      upc_list: ["012345678905"],
    };
    const price = {
      found: true,
      points: [30, 25, 20, 15, 10, 5, 0].map((d, i) => ({
        time: daysAgo(d),
        value: 89.99 - i * 3 + (i % 2 === 0 ? 4 : 0),
      })),
    };
    const bsr = {
      found: true,
      points: [30, 25, 20, 15, 10, 5, 0].map((d, i) => ({
        time: daysAgo(d),
        value: 4200 - i * 250,
      })),
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

    this.$body.find("#keepa-test-error").hide();
    this.$body.find("#keepa-test-body").show();
    this.render_product(details);
    this.render_stats(price, bsr, reviews);
    this.render_price_chart(price);
    this.render_bsr_chart(bsr);
    this.render_offers(offers);
    frappe.show_alert({ message: __("Showing demo data -- not real, 0 tokens spent"), indicator: "blue" });
  }

  _stat_tile(id, label) {
    return `
      <div class="col-sm-3">
        <div class="frappe-card" style="padding: 12px; text-align: center;">
          <div class="text-muted small">${label}</div>
          <div style="font-size: 20px; font-weight: 600;" id="${id}">--</div>
        </div>
      </div>
    `;
  }

  load() {
    const asin = this.$body.find("#keepa-test-asin").val().trim();
    if (!asin) {
      frappe.show_alert({ message: __("Enter an ASIN first"), indicator: "orange" });
      return;
    }

    this.$body.find("#keepa-test-body").hide();
    this.$body.find("#keepa-test-error").hide();
    this.$body.find("#keepa-test-loading").show();

    Promise.all([
      this._call("alaiy_os_connector_keepa.api.product.get_product_details", { asin }),
      this._call("alaiy_os_connector_keepa.api.product.get_price_history", { asin, price_type: "buy_box" }),
      this._call("alaiy_os_connector_keepa.api.product.get_bsr_history", { asin }),
      this._call("alaiy_os_connector_keepa.api.product.get_review_history", { asin }),
      this._call("alaiy_os_connector_keepa.api.product.get_current_offers", { asin }),
    ])
      .then(([details, price, bsr, reviews, offers]) => {
        this.$body.find("#keepa-test-loading").hide();
        this.$body.find("#keepa-test-body").show();
        this.render_product(details);
        this.render_stats(price, bsr, reviews);
        this.render_price_chart(price);
        this.render_bsr_chart(bsr);
        this.render_offers(offers);
      })
      .catch((err) => {
        this.$body.find("#keepa-test-loading").hide();
        this.$body.find("#keepa-test-error").text(err.message || "Call failed -- check the Error Log.").show();
      });
  }

  _call(method, args) {
    return new Promise((resolve, reject) => {
      frappe.call({
        method,
        args,
        callback: (r) => resolve(r.message || {}),
        error: () => reject(new Error(`${method} failed`)),
      });
    });
  }

  render_product(details) {
    if (!details.found) {
      this.$body.find("#kt-title").text("Not found");
      return;
    }
    this.$body.find("#kt-title").text(details.title || "(no title)");
    this.$body.find("#kt-brand").text(details.brand || details.manufacturer || "");
    this.$body.find("#kt-ids").html(
      `ASIN: ${frappe.utils.escape_html(details.asin)}` +
      (details.upc_list && details.upc_list.length ? ` &middot; UPC: ${details.upc_list[0]}` : ""),
    );
    if (details.images && details.images.length) {
      this.$body.find("#kt-image").attr("src", details.images[0]).show();
    } else {
      this.$body.find("#kt-image").hide();
    }
  }

  render_stats(price, bsr, reviews) {
    const lastPrice = price.points && price.points.length ? price.points[price.points.length - 1].value : null;
    const lastBsr = bsr.points && bsr.points.length ? bsr.points[bsr.points.length - 1].value : null;
    const lastRating = reviews.rating && reviews.rating.points.length
      ? reviews.rating.points[reviews.rating.points.length - 1].value : null;
    const lastReviewCount = reviews.reviews && reviews.reviews.points.length
      ? reviews.reviews.points[reviews.reviews.points.length - 1].value : null;

    this.$body.find("#kt-buybox").text(lastPrice != null ? _format_price(lastPrice) : "no data");
    this.$body.find("#kt-bsr").text(lastBsr != null ? `#${lastBsr.toLocaleString()}` : "no data");
    this.$body.find("#kt-rating").text(lastRating != null ? `${lastRating.toFixed(1)} / 5` : "no data");
    this.$body.find("#kt-reviews").text(lastReviewCount != null ? lastReviewCount.toLocaleString() : "no data");
  }

  render_price_chart(price) {
    this._destroy("price");
    if (!price.points || !price.points.length) {
      $("#kt-chart-price").html('<div class="text-muted">No price history yet.</div>');
      return;
    }
    this.charts.price = new frappe.Chart("#kt-chart-price", {
      data: {
        labels: price.points.map((p) => frappe.datetime.str_to_user(p.time.slice(0, 10))),
        datasets: [{ name: "Buy Box Price", values: price.points.map((p) => p.value) }],
      },
      type: "line",
      height: 220,
      colors: ["#5e64ff"],
    });
  }

  render_bsr_chart(bsr) {
    this._destroy("bsr");
    if (!bsr.points || !bsr.points.length) {
      $("#kt-chart-bsr").html('<div class="text-muted">No BSR history yet.</div>');
      return;
    }
    // frappe.Chart has no built-in axis invert -- plot negated rank so a
    // rising line still reads as "getting better" without a misleading
    // raw-rank chart where up looks like improvement when it is not.
    this.charts.bsr = new frappe.Chart("#kt-chart-bsr", {
      data: {
        labels: bsr.points.map((p) => frappe.datetime.str_to_user(p.time.slice(0, 10))),
        datasets: [{ name: "BSR (inverted, higher = better rank)", values: bsr.points.map((p) => -p.value) }],
      },
      type: "line",
      height: 220,
      colors: ["#ff5858"],
    });
  }

  render_offers(offers) {
    const $t = this.$body.find("#kt-offers-table");
    if (!offers.found || !offers.offers || !offers.offers.length) {
      $t.html('<div class="text-muted">No live offers data.</div>');
      return;
    }
    // Offers are already decoded server-side (keepa/offers.py) -- real
    // price/shipping pulled from offerCSV, condition as a label, freshness
    // flagged, not the raw Keepa offer object.
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
}
