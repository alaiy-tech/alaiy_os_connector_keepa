const KEEPA_SYNC_TYPE_COLORS = {
	watchlist: "blue",
	on_demand: "cyan",
};

const KEEPA_TRIGGER_COLORS = {
	scheduled: "purple",
	manual: "pink",
};

const KEEPA_STATUS_COLORS = {
	queued: "grey",
	running: "blue",
	success: "green",
	failed: "red",
	skipped: "yellow",
};

function alaiy_pill(value, colors) {
	if (!value) return "";
	const color = colors[value] || "darkgrey";
	return `<span class="indicator-pill ${color} filterable" data-filter="=,${value}">
		<span>${frappe.utils.escape_html(value)}</span>
	</span>`;
}

frappe.listview_settings["Keepa Sync Log"] = {
	get_indicator(doc) {
		return [
			__(doc.status),
			KEEPA_STATUS_COLORS[doc.status] || "darkgrey",
			`status,=,${doc.status}`,
		];
	},
	formatters: {
		sync_type: (value) => alaiy_pill(value, KEEPA_SYNC_TYPE_COLORS),
		trigger: (value) => alaiy_pill(value, KEEPA_TRIGGER_COLORS),
		status: (value) => alaiy_pill(value, KEEPA_STATUS_COLORS),
	},
};
