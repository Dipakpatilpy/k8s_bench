frappe.ui.form.on('Bench Settings', {
	refresh: frm => {
		frm.remove_custom_button(__("Get App"));
        frm.remove_custom_button(__("Update"));
	},
});
