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
  },
});
