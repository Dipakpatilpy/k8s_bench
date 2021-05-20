frappe.ui.form.on('Site', {
	refresh: frm => {
		frm.remove_custom_button(__("Create Alias"));
        frm.remove_custom_button(__("Delete Alias"));
	},
});
