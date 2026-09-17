frappe.pages["keepa-test"].on_page_load = function (wrapper) {
  const page = frappe.ui.make_app_page({
    parent: wrapper,
    title: "Keepa Test",
    single_column: true,
  });

  new KeepaTestPage(page);
};

// Deliberately only the free/1-token methods -- the expensive ones
// (bestsellers/top-sellers at 50, full lightning-deals list at 500) are not
// worth a click-to-test UI; use bench console for those, once, if needed.
const METHODS = [
  { label: "Price History", cost: "1 token", method: "alaiy_os_connector_keepa.api.product.get_price_history" },
  { label: "BSR History", cost: "1 token", method: "alaiy_os_connector_keepa.api.product.get_bsr_history" },
  { label: "Buy Box History", cost: "1 token", method: "alaiy_os_connector_keepa.api.product.get_buy_box_history" },
  { label: "Review History", cost: "1 token", method: "alaiy_os_connector_keepa.api.product.get_review_history" },
  { label: "Product Details", cost: "1 token", method: "alaiy_os_connector_keepa.api.product.get_product_details" },
  { label: "Current Offers", cost: "1 token", method: "alaiy_os_connector_keepa.api.product.get_current_offers" },
  { label: "Lightning Deal (this ASIN)", cost: "1 token", method: "alaiy_os_connector_keepa.api.lightning_deals.get_lightning_deal" },
];

class KeepaTestPage {
  constructor(page) {
    this.page = page;
    this.$body = $(page.body);
    this.render();
  }

  render() {
    this.$body.append(`
      <div style="max-width: 900px;">
        <p class="text-muted">
          Free/cheap methods only (issue #297's 7 whitelisted methods + product
          details + a single-ASIN lightning-deal check). Test Connection on the
          <a href="/app/keepa-connector-settings">Keepa Connector Settings</a>
          page is free -- do that first to confirm the key works before
          spending anything here.
        </p>
        <div class="form-group">
          <label>ASIN</label>
          <input type="text" class="form-control" id="keepa-test-asin" placeholder="e.g. B0F3GWXLTS" style="max-width: 300px;">
        </div>
        <div id="keepa-test-buttons" class="text-right" style="margin-bottom: 12px;"></div>
        <div id="keepa-test-result"></div>
      </div>
    `);

    const $buttons = this.$body.find("#keepa-test-buttons");
    METHODS.forEach((m) => {
      $(`<button class="btn btn-default btn-sm" style="margin: 0 4px 8px 0;">
           ${frappe.utils.escape_html(m.label)}
           <span class="text-muted">(${m.cost})</span>
         </button>`)
        .on("click", () => this.run(m))
        .appendTo($buttons);
    });
  }

  run(m) {
    const asin = this.$body.find("#keepa-test-asin").val().trim();
    if (!asin) {
      frappe.show_alert({ message: __("Enter an ASIN first"), indicator: "orange" });
      return;
    }

    const $result = this.$body.find("#keepa-test-result");
    $result.html(`<div class="text-muted">${__("Calling {0}...", [m.label])}</div>`);

    frappe.call({
      method: m.method,
      args: { asin },
      callback: (r) => {
        const pretty = JSON.stringify(r.message, null, 2);
        $result.html(`
          <div class="text-muted" style="margin-bottom: 4px;">${frappe.utils.escape_html(m.label)}:</div>
          <pre style="max-height: 500px; overflow: auto;">${frappe.utils.escape_html(pretty)}</pre>
        `);
      },
      error: () => {
        $result.html(`<div class="text-danger">${__("Call failed -- check the Error Log for details.")}</div>`);
      },
    });
  }
}
