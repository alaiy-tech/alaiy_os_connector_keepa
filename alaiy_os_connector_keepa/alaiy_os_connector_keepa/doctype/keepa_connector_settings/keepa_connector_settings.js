frappe.ui.form.on("Keepa Connector Settings", {
  refresh(frm) {
    frm.page.set_title(__("Keepa Settings"));

    // Mount the shared Alaiy OS connector status card + password reveal.
    alaiy_os.connector_card.mount(frm, "keepa");
    alaiy_os.connector_card.setup_password_reveal(
      frm,
      "keepa_api_key",
      "keepa",
    );

    frm.add_custom_button(
      __("Test Connection"),
      () => {
        frappe.call({
          // Go through the registry wrapper (not test_connection directly)
          // so a successful test also flips the "Connector Status" card at
          // the top of this form from "Not configured" to "Connected".
          method: "alaiy_os.api.connectors.test_connector",
          args: { connector_id: "keepa" },
          callback(r) {
            const res = r.message || {};
            frappe.show_alert(
              {
                message:
                  res.message ||
                  (res.success ? __("Connected") : __("Connection failed")),
                indicator: res.success ? "green" : "red",
              },
              res.success ? 5 : 7,
            );
            frm.reload_doc();
          },
        });
      },
      __("Actions"),
    );

    frm.add_custom_button(
      __("Run Watchlist Sync"),
      () => {
        frappe.call({
          method: "alaiy_os_connector_keepa.api.sync.trigger_pull_sync",
          callback: () =>
            frappe.show_alert(
              { message: __("Watchlist sync queued"), indicator: "blue" },
              5,
            ),
        });
      },
      __("Actions"),
    );

    _render_token_balance(frm);
  },
});

function _render_token_balance(frm) {
  // Test Connection already hits the free /token endpoint and reloads this
  // doc, so the fields are always as fresh as the last real check -- this
  // just makes the raw numbers readable instead of four separate inputs.
  const tokensLeft = frm.doc.keepa_tokens_left;
  const refillRate = frm.doc.keepa_refill_rate;
  const updatedAt = frm.doc.keepa_tokens_updated_at;

  frm.dashboard.clear_headline();

  if (tokensLeft === null || tokensLeft === undefined) {
    frm.dashboard.set_headline(
      __("No token balance yet -- click \"Test Connection\" to check (free, no tokens spent)."),
    );
    return;
  }

  const isLow = tokensLeft < (refillRate || 0) * 5; // less than ~5 min of refill left
  const indicator = isLow ? "orange" : "green";
  const refillLine = refillRate
    ? __("refilling {0}/min", [refillRate])
    : "";
  const whenLine = updatedAt
    ? __("as of {0}", [frappe.datetime.comment_when(updatedAt)])
    : "";

  frm.dashboard.set_headline_alert(
    `<div class="row">
      <div class="col-xs-12">
        <span class="indicator-pill ${indicator}">
          <span>${__("{0} Keepa tokens left", [tokensLeft])}</span>
        </span>
        <span class="text-muted" style="margin-left: 8px;">${refillLine} ${whenLine}</span>
      </div>
    </div>`,
  );
}
